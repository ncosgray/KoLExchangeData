import os
import boto3
import json
import time
from subprocess import run, CompletedProcess, TimeoutExpired


debug = False

# KoL account
kol_user = os.environ.get("KOL_USER")
kol_password = os.environ.get("KOL_PASSWORD")

# In Lambda, prefer credentials from Secrets Manager when a secret is configured
kol_secret_id = os.environ.get("KOL_SECRET_ID")
if kol_secret_id:
    try:
        secret = json.loads(
            boto3.client("secretsmanager").get_secret_value(SecretId=kol_secret_id)[
                "SecretString"
            ]
        )
        kol_user = secret["username"]
        kol_password = secret["password"]
    except Exception as e:
        raise RuntimeError(
            f"Could not load KoL credentials from secret {kol_secret_id}: {e!r}. "
            'The secret must hold JSON {"username": "...", "password": "..."}; '
            "set it with infra/set_kol_secret.py."
        ) from e

# Configure S3 bucket
s3 = boto3.client("s3")
s3_bucket = os.environ.get("BUCKET_NAME")

# Set paths
function_dir = "/app"
working_dir = "/tmp/.kolmafia"
install_script = f"{function_dir}/install_kolmafia.sh"
script_name = "get_mr_a_price.ash"
script_dir = f"{working_dir}/scripts"
script_source = f"{function_dir}/{script_name}"
script_dest = f"{script_dir}/{script_name}"
run_file = f"{script_dir}/run.txt"
java_path = "/var/lang/bin/java"
jar_file = "/tmp/kolmafia/kolmafia.jar"

# Explicitly use UTF-8
env = os.environ.copy()
env.update(
    {
        "LANG": "C.utf8",
        "LC_ALL": "C.utf8",
        "LC_CTYPE": "C.utf8",
        "PYTHONIOENCODING": "utf-8",
    }
)


# Configure and validate environment
def configure_game():
    try:
        # Download and install the current version of Kolmafia
        os.system(f"bash {install_script}")

        # Create game settings directory and copy scripts into place
        os.makedirs(script_dir, exist_ok=True)
        os.system(f"cp {script_source} {script_dest}")
        with open(run_file, "w") as f:
            f.write(f"login {kol_user}\n")
            f.write(f"{kol_password}\n")
            f.write(f"call {script_name}\n")
            f.write("quit\n")

        # Validate environment
        run_ok = os.path.isfile(run_file)
        script_ok = os.path.isfile(script_dest)
        java_ok = os.path.isfile(java_path)
        jar_ok = os.path.isfile(jar_file)
        if not (run_ok and script_ok and java_ok and jar_ok):
            raise Exception(
                f"Environment check failed: run_ok={run_ok} script_ok={script_ok} java_ok={java_ok} jar_ok={jar_ok}"
            )

    except Exception as e:
        raise Exception(f"Setup error: {e}")


# Fetch exchange rate and IOTM data from the game
def fetch_data_from_game(context=None):
    cmd = [
        java_path,
        "-jar",
        "-Djava.awt.headless=true",
        "-DuseCWDasROOT=true",
        jar_file,
        "--CLI",
    ]
    retries = 5
    attempt_timeout = 60
    # Time to leave after the last attempt for saving to S3 and a clean exit
    reserve_seconds = 15

    def seconds_left():
        if context is None:
            return float("inf")
        return context.get_remaining_time_in_millis() / 1000

    for attempt in range(1, retries + 1):
        # Back off before each retry, but only if the backoff and attempt still fit
        delay = (attempt - 1) * 30
        if seconds_left() < delay + attempt_timeout + reserve_seconds:
            print(f"Attempt {attempt}: not enough time left for another attempt")
            break
        time.sleep(delay)
        print(
            f"Attempt {attempt}: Fetching exchange rate and IOTM data from the game..."
        )
        try:
            # Run kolmafia script
            data = None
            result = run(
                cmd,
                cwd=working_dir,
                stdin=open(run_file, "r"),
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=attempt_timeout,
                env=env,
            )

            # Check result
            if result.returncode != 0:
                raise Exception(f"Error running kolmafia script: {result.stderr}")
            else:
                result_data = result.stdout
                if debug:
                    print(result_data)

                # Find mall price data
                for line in result_data.split("\n"):
                    if "mall_price" in line:
                        data = json.loads(line)
                if data:
                    print(f"Current mall price: {data['mall_price']}")
                    print(f"Current IOTM: {data['iotm_name']}")
                    return data
                else:
                    # Retry if rate not found in result
                    raise Exception(f"Mall price not found in result: {result_data}")
        except TimeoutExpired as e:
            print(f"Attempt {attempt}: Timeout error: {e.output}")
        except Exception as e:
            print(f"Attempt {attempt}: Error fetching data: {e}")

    # Give up
    raise Exception("Failed to fetch data after all retries.")


# Save JSON data file to S3
def save_data_to_s3(data):
    try:
        # Arrange into folders by year
        folder = (data["game_date"])[:4]
        filename = f"{folder}/{data['game_date']}.json"

        s3.put_object(
            Body=json.dumps(data, indent=4, ensure_ascii=False),
            ContentType="application/json; charset=utf-8",
            Bucket=s3_bucket,
            Key=filename,
        )
        print(f"Data saved to S3 as {filename}")
    except Exception as e:
        raise Exception(f"Error saving data to S3: {e}")


# Lambda handler
def handler(event, context):
    main(context)


# Main function
def main(context=None):
    try:
        configure_game()
        data = fetch_data_from_game(context)
        if data:
            save_data_to_s3(data)
    except Exception as e:
        raise Exception(f"Script failed with error: {e}")
    else:
        print("Finished running the script.")


if __name__ == "__main__":
    main()
