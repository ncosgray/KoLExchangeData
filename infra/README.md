# KolExchangeStack (AWS CDK)

Deploys the three Lambda functions (upload, process, data API), an HTTP API, and optionally the
daily schedule and S3 trigger.

The S3 buckets and their bucket policies, the DynamoDB table, the KoL credentials secret, and
the HTTP API (with its stage, route, and integration) are pre-existing resources **imported**
into the stack with `cdk import`. Their definitions in `kol_exchange/stack.py` mirror their real
configuration, and they use `RemovalPolicy.RETAIN`, so CDK never deletes them. Importing the API
keeps its execute-api URL, which is tied to the API ID and could never be recreated.

The stack manages the secret but never its value: the template has no `SecretString`, so a
deploy can't overwrite or regenerate the credentials. Set the value with the CLI (below).

## Settings

Read from `../.devcontainer/devcontainer.env` (or the same variables in your shell); see
`devcontainer.env.sample`. Only these keys are used, and nothing account-specific is
hard-coded in this repo:

| Variable | Purpose |
| --- | --- |
| `AWS_DEFAULT_REGION` | Region to deploy to. `set_kol_secret.py` uses it too |
| `KOL_BUCKET_NAME` | Raw data bucket |
| `KOL_WEB_BUCKET_NAME` | Web output bucket |
| `KOL_TABLE_NAME` | DynamoDB table |
| `KOL_AWS_APPLICATION_ARN` | Optional: myApplications ARN for the `awsApplication` tag. Set it if the existing resources already have this tag, or a deploy will remove it |

Other options (secret name, IAM user granted access in the raw bucket policy, schedule,
triggers) are in `cdk.json`.

`kol:enableTriggers` turns the daily schedule and the raw bucket's S3 trigger on or off, for
example to pause the pipeline. Change it in `cdk.json`, not with `-c` on the command line: a
`-c` value applies to that one command only, so the next plain `cdk deploy` quietly undoes it.

## AWS credentials: use an admin profile

Run every `cdk` command, and the `aws` commands below, as an **IAM admin identity**, not the
restricted IAM user from `devcontainer.env`. That user can't bootstrap or deploy
(e.g. `not authorized to perform: cloudformation:CreateChangeSet`).

```bash
aws configure --profile <admin-profile>     # one time
export AWS_PROFILE=<admin-profile>

# Exported dev-container keys take precedence over the profile, so clear them
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN

aws sts get-caller-identity                 # confirm the ARN is your admin user
```

Run these from a regular terminal, not inside a dev container (it loads the restricted keys).

`cdk` and `set_kol_secret.py` always use the region in
`AWS_DEFAULT_REGION` (see Settings), whatever your profile's default region is. Other `aws`
commands, such as tagging or invoking functions by hand, use the profile's region, so add
`--region` if it differs.

## One-time setup

Needs Python 3.9 or later.

```bash
npm install -g aws-cdk
cd infra
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cdk bootstrap
```

### KoL credentials

The upload function reads `{"username": "...", "password": "..."}` from the secret. In a fresh
account `cdk deploy` creates the secret empty. To set or change the value, run from `infra/`:

```bash
python3 set_kol_secret.py
```

It prompts for the username and password (without echoing the password) and passes them to
the AWS CLI on stdin, so they never reach a file, a command line, or shell history. It writes
the secret named by `kol:secretName` in `cdk.json`, in the deploy region.

## Deploy

```bash
cdk diff
cdk deploy
```

Docker must be running: `cdk deploy` builds both container images and pushes them to the CDK
assets repository, replacing `docker_build.sh`.
