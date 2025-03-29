# KoL Exchange Rate Data

[![GitHub license](https://img.shields.io/github/license/ncosgray/KoLExchangeData?color=lightgrey)](https://github.com/ncosgray/KoLExchangeData/blob/master/LICENSE.txt)

*What the heck is this?* These are Docker container definitions.

I wanted to find a way to use [Kolmafia](https://wiki.kolmafia.us/) to fully automate downloading and processing Mr. Accessory mall price data from The Kingdom of Loathing every day -- the dataset that feeds the graphs at the [KoL Exchange Rate website](https://www.nathanatos.com/kol-exchange-rate/) and its companion [Android app](https://github.com/ncosgray/KoLExchangeWidget).

This set of Docker containers, designed to run as AWS Lambda functions, is my best effort at doing so.

## Dev Environment

#### Prerequisites

* Docker
* AWS
* Kingdom of Loathing login
* VS Code with Dev Containers extension (for testing)
* a bit of wonkiness

#### Configuration

At a minimum, you will need to configure the following AWS resources, including adding roles and permissions to each resource as necessary. Refer to [AWS Documentation](https://docs.aws.amazon.com).

* **IAM** user and role(s)
* **Elastic Container Registry** repos to store the containers
* **Lambda** functions to run the container code
* **S3** and **DynamoDB** for exchange rate data storage
* **CloudWatch** script logs
* **EventBridge** if you want to run on a schedule

Then, set these environment variables on your computer:

| Local environment variable | Lambda environment variable | Purpose |
| :--: | :--: | :--: |
| `AWS_ACCESS_KEY_ID` | n/a | access key for the IAM user |
| `AWS_SECRET_ACCESS_KEY` | n/a | secret for the IAM user |
| `AWS_DEFAULT_REGION` | n/a | AWS region |
| `KOL_BUCKET_NAME` | `BUCKET_NAME` | S3 bucket name for collecting raw data |
| `KOL_WEB_BUCKET_NAME` | `WEB_BUCKET_NAME` | S3 bucket name for outputting graphs |
| `KOL_TABLE_NAME` | `TABLE_NAME` | DynamoDB table name for data storage |
| `KOL_USER` | `KOL_USER` | Kingdom of Loathing username |
| `KOL_PASSWORD` | `KOL_PASSWORD` | Kingdom of Loathing password |

Open the KolExchangeData repo in VS Code, installing the Dev Containers extension if necessary. You will be prompted to choose a container (see below for a description of each container). After you do so, things should boot up into an environment where you can test uploading data or generating graphs simply by running `python app.py`.

## The Containers

#### kol-exchange-upload

This container downloads the latest version of [Kolmafia](https://wiki.kolmafia.us/) and uses it to collect information  from the game related to Mr. Accessory. Output is added as JSON to an S3 bucket.

*Scripts:*

* **app.py** is a Python script to orchestrate the process. After doing some initial setup to move scripts into the expected locations, we then call the [ASH](https://wiki.kolmafia.us/index.php?title=Ash_Functions) script, collect the output, and send it to the raw data S3 bucket. Log messages are sent to CloudWatch along the way.

* **get_mr_a_price.ash** connects to the game to collect data about the Mr. Accessory selling price and the Item-of-the-Month (IOTM) (or FOTM!) currently available in Mr. Store. The output of this script is a simple JSON string containing the following elements:

| Field | Type | Contents |
| :--: | :--: | :--: |
| `mall_price` | integer | mall price of Mr. Accessory |
| `rate` | integer | exchange rate, i.e. mall_price / 10 |
| `iotm_id` | integer | ID of current IOTM |
| `iotm_name` | string | name of current IOTM |
| `iotm_is_familiar` | boolean | true if current IOTM is a familiar |
| `game_date` | string | in-game date |
| `now` | string | UTC date and time of script execution |

#### kol-exchange-process

This container is designed to run on a trigger whenever a new exchange rate file appears in the raw data S3 bucket. New data is inserted into a database table for easy querying. Then, the full dataset is used to generate a number of history graphs.

*Scripts:*

* **app.py** does all the processing. First, it checks to see if an event has fired indicating that a new JSON object has been added to the S3 raw datastore. If so, its contents are added to the DynamoDB database table. The script then runs a query against DynamoDB to extract the full exchange rate historical dataset, divides it into date ranges, and uses [matplotlib](https://matplotlib.org/) to generate a series of PNG graphs. These PNGs are uploaded to a second S3 bucket meant to be accessed via web requests.

## Deployment

Set your local environment variable `KOL_ECR` to the location of your AWS Elastic Container Registry. Then run the `docker_build.sh` script, passing the container name as an argument, to build and push the image to ECR.

Point your Lambda function to your ECR repo. Add environment variables corresponding to the local variables you set up when you were testing.

Once everything is in place in AWS, you can test the function with `aws lambda invoke`, an EventBridge schedule, and/or a trigger that fires when new data lands in S3.

## About

Author: [Nathan Cosgray](https://www.nathanatos.com)
