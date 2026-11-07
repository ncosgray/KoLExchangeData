#!/usr/bin/env python3
"""Set the KoL credentials secret, {"username": "...", "password": "..."}, that the upload
function reads.

Prompts for the username and password (the password without echoing it) and hands the value
to the AWS CLI on stdin, so it never reaches a file, a command line, or shell history. Writes
the secret named by kol:secretName in cdk.json, in the deploy region (AWS_DEFAULT_REGION from
the settings), whatever the profile's default region is.

Usage, from infra/ as an admin identity: python3 set_kol_secret.py
"""

import getpass
import json
import subprocess
import sys
from pathlib import Path

from kol_exchange.settings import load_settings

CDK_JSON = Path(__file__).resolve().parent / "cdk.json"


def main() -> int:
    region = load_settings()["AWS_DEFAULT_REGION"]
    secret_id = json.loads(CDK_JSON.read_text())["context"]["kol:secretName"]
    print(f"Setting secret {secret_id} in {region}")
    try:
        username = input("KoL username: ").strip()
        password = getpass.getpass("KoL password: ")
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled; secret not changed.", file=sys.stderr)
        return 1
    if not username or not password:
        print("Username and password are both required; secret not changed.", file=sys.stderr)
        return 1
    result = subprocess.run(
        [
            "aws",
            "secretsmanager",
            "put-secret-value",
            "--region",
            region,
            "--secret-id",
            secret_id,
            "--secret-string",
            "file:///dev/stdin",
        ],
        input=json.dumps({"username": username, "password": password}),
        text=True,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
