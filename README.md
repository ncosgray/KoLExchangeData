# KoL Exchange Rate Data

[![GitHub license](https://img.shields.io/github/license/ncosgray/KoLExchangeData?color=lightgrey)](https://github.com/ncosgray/KoLExchangeData/blob/master/LICENSE.txt)

*What the heck is this?* It's a Docker container definition.

I wanted to find a way to use [KoLmafia](https://wiki.kolmafia.us/) to fully automate downloading Mr. Accessory mall price data from The Kingdom of Loathing every day -- the dataset that feeds the graphs at the [KoL Exchange Rate website](https://www.nathanatos.com/kol-exchange-rate/) and its companion [Android app](https://github.com/ncosgray/KoLExchangeWidget).

This Docker container, designed to run as an AWS Lambda function, is my best effort at doing so.

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
* **Elastic Container Registry** repo to store the container
* **Lambda** function to run the container code
* **S3** for exchange rate data storage
* **CloudWatch** script logs
* **EventBridge** if you want to run on a schedule

Then, set these environment variables on your computer:

| Local environment variable | Lambda environment variable | Purpose |
| :--: | :--: | :--: |
| `AWS_ACCESS_KEY_ID` | n/a | access key for the IAM user |
| `AWS_SECRET_ACCESS_KEY` | n/a | secret for the IAM user |
| `AWS_DEFAULT_REGION` | n/a | AWS region |
| `KOL_BUCKET_NAME` | `BUCKET_NAME` | S3 bucket name for output |
| `KOL_LOG_GROUP_NAME` | `LOG_GROUP_NAME` | CloudWatch log group |
| `KOL_LOG_STREAM_NAME` | `LOG_STREAM_NAME` | CloudWatch log stream |
| `KOL_USER` | `KOL_USER` | Kingdom of Loathing username |
| `KOL_PASSWORD` | `KOL_PASSWORD` | Kingdom of Loathing password |

Open the KolExchangeData repo in VS Code, installing the Dev Containers extension if necessary. Things should boot up into an environment where you can test the upload process simply by running `python app.py`.

#### The Scripts

* **app.py** is a Python script to orchestrate the process. After doing some initial setup to move scripts into the expected locations, we then call the ASH script, collect the output, and send it to an S3 bucket. Log messages are sent to CloudWatch along the way.

* **get_mr_a_price.ash** connects to the game to collect data about the Mr. Accessory selling price and the Item-of-the-Month (IOTM) currently available in Mr. Store. The output of this script is a simple JSON string containing the following elements:

| Field | Type | Contents |
| :--: | :--: | :--: |
| `mall_price` | integer | lowest price of Mr. Accessory |
| `rate` | integer | exchange rate, i.e. mall_price / 10 |
| `iotm_id` | integer | ID of current IOTM |
| `iotm_name` | string | name of current IOTM |
| `iotm_is_familiar` | boolean | true if current IOTM is a familiar |
| `game_date` | string | in-game date |
| `now` | string | UTC date and time of script execution |

#### Deployment

Set your local environment variables `KOL_ECR` and `KOL_ECR_REPO` to the ID and URI of the AWS Elastic Container Registry repo. Then run the `utils/docker_build.sh` script on your local machine to build and push the image.

Point your Lambda function to your ECR repo. Add environment variables corresponding to the local variables you set up when you were testing.

Once everything is in place in AWS, you can test the function with `aws lambda invoke`, or an EventBridge schedule.

## About

Author: [Nathan Cosgray](https://www.nathanatos.com)
