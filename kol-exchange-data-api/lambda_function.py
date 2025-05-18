import datetime
import boto3
import json
import os
from botocore.exceptions import ClientError

# Initialize the S3 client
s3 = boto3.client('s3')
bucket_name = os.environ.get('BUCKET_NAME')

# Required date format for parameter requests
date_format = '%Y%m%d'


# Function to find an object by date
def find_object_by_date(date):
    # Rate data is grouped into folders by year
    object_key = f"{date.year}/{date.strftime(date_format)}.json"
    try:
        # Try to get the object from S3
        response = s3.get_object(Bucket=bucket_name, Key=object_key)
        return response['Body'].read().decode('utf-8')
    except ClientError as e:
        # If object does not exist, return None
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        # For other errors, raise the error
        raise e
    

def lambda_handler(event, context):
    # Get the parameter from the event (if any)
    date_param = event.get('queryStringParameters', {}).get('date', None)
    xml_param = event.get('queryStringParameters', {}).get('xml', None)

    # If a date parameter is provided, use it; otherwise, use today
    if date_param:
        try:
            # Validate and parse the provided date
            requested_date = datetime.datetime.strptime(date_param, date_format).date()
            
            # Try to find the object for this date
            result = find_object_by_date(requested_date)
        except ValueError:
            # If the date format is invalid, return a 400 error
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'message': f"Invalid date format. Please provide a date in the format {date_format}"
                }),
                'headers': {
                    'Content-Type': 'application/json'
                }
            }
    else:
        # Try to find an object for today and backtrack up to 30 days
        today = datetime.datetime.now().date()
        for days_back in range(0, 31):
            date_to_check = today - datetime.timedelta(days=days_back)
            
            # Try to find the object for this date
            result = find_object_by_date(date_to_check)
            if result:
                break
    
    # If an object is found, return the contents in the requested format
    if result and xml_param:
        # Return the XML version of the object
        result_dict = json.loads(result)
        if 'rate' in result_dict:
            return f"<rate>{result_dict['rate']:,} Meat</rate>"
    if result is not None:
        # Return the default JSON
        return result

    # If no object was found, return an error
    else:
        return {
            'statusCode': 404,
            'body': json.dumps({
                'message': 'Object not found.'
            }),
            'headers': {
                'Content-Type': 'application/json'
            }
    }
