import datetime
import boto3
import json
import os
from botocore.exceptions import ClientError

# Initialize the S3 client
s3 = boto3.client("s3")
bucket_name = os.environ.get("BUCKET_NAME")

# Required date format for parameter requests
date_format = "%Y%m%d"


# Generate an error
def error_object(message, statusCode=500):
    return {
        "statusCode": statusCode,
        "body": json.dumps({"message": message}),
        "headers": {"Content-Type": "application/json"},
    }


# Function to find an object by date
def find_object_by_date(date):
    # Rate data is grouped into folders by year
    object_key = f"{date.year}/{date.strftime(date_format)}.json"
    try:
        # Try to get the object from S3
        response = s3.get_object(Bucket=bucket_name, Key=object_key)
        return response["Body"].read().decode("utf-8")
    except ClientError as e:
        # If object does not exist, return None
        if e.response["Error"]["Code"] == "NoSuchKey":
            return None
        # For other errors, raise the error
        raise e


# Fetch data from S3 based on supplied parameters
def fetch_data(date_param=None, xml_param=None):
    # If a date parameter is provided, use it; otherwise, use today
    if date_param:
        try:
            # Validate and parse the provided date
            requested_date = datetime.datetime.strptime(date_param, date_format).date()

            # Try to find the object for this date
            result = find_object_by_date(requested_date)
        except ValueError:
            # If the date format is invalid, return an error
            return error_object(
                f"Invalid date format. Please provide a date in the format {date_format}",
                statusCode=400,
            )
        except Exception as e:
            return error_object("Data retrieval error.")
    else:
        # Try to find an object for today and backtrack up to 30 days
        today = datetime.datetime.now().date()
        for days_back in range(0, 31):
            date_to_check = today - datetime.timedelta(days=days_back)

            # Try to find the object for this date
            try:
                result = find_object_by_date(date_to_check)
                if result:
                    break
            except Exception as e:
                return error_object("Data retrieval error.")

    # If an object is found, return the contents in the requested format
    if result:
        try:
            result_dict = json.loads(result)
            rate = f"{result_dict.get('rate', 0):,} Meat"
            if xml_param:
                # Return the XML version of the object (formatted rate only)
                return f"<rate>{rate}</rate>"
            else:
                # Return the default JSON with formatted rate and IOTM info added
                result_dict["rate_formatted"] = f"$1 US = {rate}"
                iotm_label = (
                    "FOTM" if result_dict.get("iotm_is_familiar", False) else "IOTM"
                )
                result_dict["iotm_formatted"] = (
                    f"{iotm_label}: {result_dict.get('iotm_name', '?')}"
                )
                return result_dict
        except Exception as e:
            return error_object("Data parsing error.")

    # If no object was found, return an error
    else:
        return error_object("No data found.", statusCode=404)


# Lambda handler
def lambda_handler(event, context):
    # Get the parameter from the event (if any)
    date_param = event.get("queryStringParameters", {}).get("date", None)
    xml_param = event.get("queryStringParameters", {}).get("xml", None)

    data = fetch_data(date_param, xml_param)
    return data


# ### For local testing
# print(
#     fetch_data(
#         date_param="20250802",  # Example date parameter (set to None for today)
#         xml_param=None,  # Example XML parameter (set to any value for XML output)
#     )
# )
