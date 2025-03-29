import boto3
import json
import matplotlib.pyplot as plt
import os
import pandas as pd
import urllib.parse
from datetime import datetime, timedelta, timezone
from dynamo_pandas import get_df

# Initialize S3 and DynamoDB clients
s3 = boto3.client("s3")
s3_bucket = os.environ.get("WEB_BUCKET_NAME")
db = boto3.client("dynamodb")
table_name = os.environ.get("TABLE_NAME")

# Plot file output
output_dir = os.environ.get("MPLCONFIGDIR")
file_prefix = "rate_history"
file_type = "png"


# Plot exchange rate data and upload to S3 bucket
def plot_data(data: pd.DataFrame, iotm: pd.DataFrame, output_file: str):
    try:
        # Set formatting
        number_formatter = plt.matplotlib.ticker.StrMethodFormatter("{x:,.0f}")
        date_locator = plt.matplotlib.dates.AutoDateLocator(minticks=3, maxticks=7)
        date_formatter = plt.matplotlib.dates.ConciseDateFormatter(date_locator)

        # Generate the plot
        plt.figure()
        plt.plot(data["rate"], color="r")
        plt.plot(
            iotm.loc[iotm["iotm_is_familiar"] == 1]["rate"],
            linestyle="",
            marker="o",
            color="g",
        )
        plt.plot(
            iotm.loc[iotm["iotm_is_familiar"] == 0]["rate"],
            linestyle="",
            marker="o",
            color="b",
        )
        plt.xlabel("DATE")
        plt.gca().xaxis.set_major_formatter(date_formatter)
        plt.ylabel("MEAT / USD")
        plt.gca().yaxis.set_major_formatter(number_formatter)
        plt.legend(["Exchange Rate", "New Mr. Store FOTM", "New Mr. Store IOTM"])
        plt.grid()

        # Save to temp file and upload to S3
        output_path = f"{output_dir}/{output_file}"
        plt.savefig(output_path, dpi=600, bbox_inches="tight")
        s3.upload_file(output_path, s3_bucket, output_file)

        plt.close()
    except Exception as e:
        raise e


# Generate plots for various time periods
def generate_plots():
    try:
        # Get data from DynamoDB
        df = get_df(table=table_name)
        print(f"Got {len(df)} days of history from the database.")

        # Exchange rate sorted by date
        df["date"] = pd.to_datetime(df["game_date"], utc=True)
        df.set_index("date", inplace=True)
        df.sort_index(inplace=True)

        # IOTM records sorted by date
        iotm = df.groupby(["iotm_name", "iotm_is_familiar"]).first().reset_index()
        iotm["date"] = pd.to_datetime(iotm["game_date"], utc=True)
        iotm.set_index("date", inplace=True)
        iotm.sort_index(inplace=True)

        # Plot: all time
        print(f"Plotting full history...")
        plot_data(df, iotm, f"{file_prefix}.{file_type}")

        # Plot: monthly data
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        plot_months = [1, 3, 6, 12, 24, 36, 48, 60, 72, 84, 96, 108, 120, 180]
        for months in plot_months:
            begin_date = (
                (now - timedelta(days=months * 30)).replace(day=1).strftime("%Y-%m-%d")
            )
            print(f"Plotting {begin_date} through {today}...")
            plot_data(
                df.loc[begin_date:today],
                iotm.loc[begin_date:today],
                f"{file_prefix}_{months}mo.{file_type}",
            )
    except Exception as e:
        raise Exception(f"Error generating plot: {e}")


# Add rate data from S3 to database
def add_rate_data(data):
    try:
        item = {
            "mall_price": {"N": str(data["mall_price"])},
            "rate": {"N": str(data["rate"])},
            "iotm_id": {"N": str(data["iotm_id"])},
            "iotm_name": {"S": data["iotm_name"]},
            "iotm_is_familiar": {"BOOL": data["iotm_is_familiar"] == "True"},
            "game_date": {"S": data["game_date"]},
            "now": {"S": data["now"]},
        }

        # Insert this item into the DynamoDB table
        db.put_item(TableName=table_name, Item=item)
    except Exception as e:
        raise e


# Lambda handler
def handler(event, context):
    # Get S3 object from the triggering event
    if event:
        bucket = event["Records"][0]["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(
            event["Records"][0]["s3"]["object"]["key"], encoding="utf-8"
        )
        try:
            # Read object contents into JSON dict and add to table
            response = s3.get_object(Bucket=bucket, Key=key)
            data = json.loads(response["Body"].read().decode("utf-8"))
            add_rate_data(data)
        except Exception as e:
            raise Exception(f"Error updating database: {e}")
        else:
            print(f"Database updated with key {key}.")

    # Generate and upload plot images
    generate_plots()


# Main function
def main():
    # Only generate plots
    generate_plots()


if __name__ == "__main__":
    main()
