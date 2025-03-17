import os
import boto3
import json
import time
from subprocess import run, CompletedProcess, TimeoutExpired


debug = False

# KoL account
kol_user = os.environ.get("KOL_USER")
kol_password = os.environ.get("KOL_PASSWORD")

# Configure S3 bucket
s3 = boto3.client("s3")
s3_bucket = os.environ.get("BUCKET_NAME")

# Configure CloudWatch Logs client
logs = boto3.client("logs")
log_group_name = os.environ.get("LOG_GROUP_NAME")
log_stream_name = os.environ.get("LOG_STREAM_NAME")

# Set paths
function_dir = "/app"
working_dir = "/tmp/.kolmafia"
script_name = "get_mr_a_price.ash"
script_path = working_dir + "/scripts"
script_source = function_dir + "/" + script_name
script_dest = script_path + "/" + script_name
run_file = script_path + "/run.txt"
java_path = "/var/lang/bin/java"
jar_path = function_dir + "/kolmafia/kolmafia.jar"


# Configure and validate environment
def configure_game():
    try:
        # Create game settings directory and copy scripts into place
        os.makedirs(script_path, exist_ok=True)
        os.system(f"cp {script_source} {script_dest}")
        os.system(f'echo "login {kol_user}" > {run_file}')
        os.system(f'echo "{kol_password}" >> {run_file}')
        os.system(f'echo "call {script_name}" >> {run_file}')
        os.system(f'echo "quit" >> {run_file}')

        # Validate environment
        run_ok = os.path.isfile(run_file)
        script_ok = os.path.isfile(script_dest)
        java_ok = os.path.isfile(java_path)
        jar_ok = os.path.isfile(jar_path)
        if not (run_ok and script_ok and java_ok and jar_ok):
            raise Exception(
                f"Environment check failed: run_ok={run_ok} script_ok={script_ok} java_ok={java_ok} jar_ok={jar_ok}"
            )

    except Exception as e:
        raise Exception(f"Setup error: {e}")


# Fetch exchange rate and IOTM data from the game
def fetch_data_from_game():
    cmd = [
        java_path,
        "-jar",
        "-Djava.awt.headless=true",
        "-DuseCWDasROOT=true",
        jar_path,
        "--CLI",
    ]
    retries = 5
    for attempt in range(1, retries):
        log_message(
            f"Attempt {attempt}: Fetching exchange rate and IOTM data from the game...",
            level="INFO",
        )
        try:
            # Run kolmafia script
            data = None
            result = run(
                cmd,
                cwd=working_dir,
                stdin=open(run_file, "r"),
                check=True,
                text=True,
                capture_output=True,
                timeout=60,
            )

            # Check result
            if result.returncode != 0:
                raise Exception(f"Error running kolmafia script: {result.stderr}")
            else:
                result_data = result.stdout
                if debug:
                    log_message(result_data, level="INFO")

                # Find mall price data
                for line in result_data.split("\n"):
                    if "mall_price" in line:
                        data = json.loads(line)
                if data:
                    log_message(
                        f"Current mall price: {data['mall_price']}", level="INFO"
                    )
                    return data
                else:
                    # Retry if rate not found in result
                    raise Exception("Mall price not found in result.")
        except TimeoutExpired as e:
            log_message(f"Attempt {attempt}: Timeout error: {e.output}", level="ERROR")
            time.sleep(attempt * 30)
        except Exception as e:
            log_message(f"Attempt {attempt}: Error fetching data: {e}", level="ERROR")
            time.sleep(attempt * 30)

    # Give up
    raise Exception("Failed to fetch data after all retries.")


# Save JSON data file to S3
def save_data_to_s3(data):
    try:
        # Arrange into folders by year
        folder = (data["game_date"])[:4]
        filename = f"{folder}/{data['game_date']}.json"

        s3.put_object(Body=json.dumps(data, indent=4), Bucket=s3_bucket, Key=filename)
        log_message(f"Data saved to S3: {filename}", level="INFO")
    except Exception as e:
        raise Exception(f"Error saving data to S3: {e}", level="ERROR")


# Log function for AWS CloudWatch
def log_message(message, level="INFO"):
    if debug:
        print(message)
    else:
        try:
            # Write to CloudWatch Logs
            logs.put_log_events(
                logGroupName=log_group_name,
                logStreamName=log_stream_name,
                logEvents=[
                    {
                        "timestamp": int(time.time() * 1000),
                        "message": f"{level}: {message}",
                    }
                ],
            )
        except Exception as e:
            print(f"Error logging to CloudWatch: {e}")


# Main function
def main():
    try:
        configure_game()
        data = fetch_data_from_game()
        if data:
            save_data_to_s3(data)
    except Exception as e:
        log_message(f"Script failed with error: {e}", level="ERROR")
    finally:
        log_message("Finished running the script.", level="INFO")


# Lambda handler
def handler(event, context):
    main()


if __name__ == "__main__":
    main()
