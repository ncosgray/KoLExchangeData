"""Deployment settings, shared by the CDK app and the helper scripts.

Non-secret settings are read from the shell environment, falling back to the dev container
env file. Only these keys are read; credentials in the file are ignored, and nothing
account-specific is hard-coded in this repo.
"""

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[2] / ".devcontainer" / "devcontainer.env"
SETTINGS = ("AWS_DEFAULT_REGION", "KOL_BUCKET_NAME", "KOL_WEB_BUCKET_NAME", "KOL_TABLE_NAME")
OPTIONAL_SETTINGS = ("KOL_AWS_APPLICATION_ARN",)  # myApplications ARN for the awsApplication tag
ALL_SETTINGS = SETTINGS + OPTIONAL_SETTINGS


def load_settings() -> dict:
    values = {key: os.environ.get(key) for key in ALL_SETTINGS}
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text().splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and key in ALL_SETTINGS and value and not values[key]:
                values[key] = value.strip().strip('"').strip("'")
    missing = [key for key in SETTINGS if not values[key]]
    if missing:
        raise SystemExit(f"Missing settings (set in {ENV_FILE} or environment): {missing}")
    return values
