#!/usr/bin/env python3
import os
import sys

import aws_cdk as cdk

from kol_exchange.settings import load_settings
from kol_exchange.stack import KolExchangeStack

settings = load_settings()
if not settings["KOL_AWS_APPLICATION_ARN"]:
    print(
        "WARNING: KOL_AWS_APPLICATION_ARN is not set. If the imported buckets or table "
        "already have an awsApplication tag, the next deploy that updates them will "
        "remove it.",
        file=sys.stderr,
    )

app = cdk.App()
KolExchangeStack(
    app,
    "KolExchangeStack",
    raw_bucket_name=settings["KOL_BUCKET_NAME"],
    web_bucket_name=settings["KOL_WEB_BUCKET_NAME"],
    table_name=settings["KOL_TABLE_NAME"],
    aws_application_arn=settings["KOL_AWS_APPLICATION_ARN"],
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=settings["AWS_DEFAULT_REGION"],
    ),
)
app.synth()
