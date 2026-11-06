from pathlib import Path
from typing import Optional

from aws_cdk import (
    ArnFormat,
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    Tags,
    TimeZone,
    aws_apigatewayv2 as apigw,
    aws_dynamodb as dynamodb,
    aws_ecr_assets as ecr_assets,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_scheduler as scheduler,
    aws_scheduler_targets as scheduler_targets,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct

# Repo root, so container/code paths match the existing project layout
REPO_ROOT = Path(__file__).resolve().parents[2]

# Tags already present on the existing buckets and table. Applied to every resource so the
# imported ones keep them exactly (a managed resource's tag list is replaced, not merged).
# Applied to the stack's children rather than the stack itself: CloudFormation stack tags
# can't have empty values, and "kol-exchange" is "".
# The account-specific myApplications ARN (awsApplication tag) is passed in from settings
# rather than hard-coded here.
APP_TAGS = {
    "kol-exchange": "",
    "app-name": "kol-exchange",
}

# Public access settings on both existing buckets (all off; public reads go via bucket policy)
PUBLIC_ACCESS_ALLOWED = s3.BlockPublicAccess(
    block_public_acls=False,
    ignore_public_acls=False,
    block_public_policy=False,
    restrict_public_buckets=False,
)


class KolExchangeStack(Stack):
    def log_group(self, construct_id: str) -> logs.LogGroup:
        """Function log group with 3-month retention, deleted along with its function."""
        return logs.LogGroup(
            self,
            construct_id,
            retention=logs.RetentionDays.THREE_MONTHS,
            removal_policy=RemovalPolicy.DESTROY,
        )

    def existing_bucket(self, construct_id: str, bucket_name: str, **overrides) -> s3.Bucket:
        """Imported bucket with the settings both existing buckets share, including the
        existing '<bucket>-stale-versions' lifecycle rule."""
        return s3.Bucket(
            self,
            construct_id,
            bucket_name=bucket_name,
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            bucket_key_enabled=True,
            block_public_access=PUBLIC_ACCESS_ALLOWED,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id=f"{bucket_name}-stale-versions",
                    enabled=True,
                    expired_object_delete_marker=True,
                    noncurrent_version_expiration=Duration.days(1),
                    abort_incomplete_multipart_upload_after=Duration.days(1),
                )
            ],
            removal_policy=RemovalPolicy.RETAIN,
            **overrides,
        )

    def container_function(
        self, construct_id: str, directory: str, environment: dict
    ) -> lambda_.DockerImageFunction:
        """Container Lambda sized like the existing hand-built ones. Build-context
        excludes come from each directory's .dockerignore."""
        return lambda_.DockerImageFunction(
            self,
            construct_id,
            code=lambda_.DockerImageCode.from_image_asset(
                str(REPO_ROOT / directory), platform=ecr_assets.Platform.LINUX_AMD64
            ),
            architecture=lambda_.Architecture.X86_64,
            memory_size=768,
            timeout=Duration.minutes(5),
            environment=environment,
            log_group=self.log_group(f"{construct_id}Logs"),
        )

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        raw_bucket_name: str,
        web_bucket_name: str,
        table_name: str,
        aws_application_arn: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        secret_name = self.node.try_get_context("kol:secretName")
        enable_triggers = str(self.node.try_get_context("kol:enableTriggers")).lower() == "true"
        schedule_cron = self.node.try_get_context("kol:scheduleCron")
        schedule_tz = self.node.try_get_context("kol:scheduleTimeZone")

        # ---- Stateful resources -------------------------------------------------------------
        # These already exist and are adopted with `cdk import`. Definitions mirror their
        # current configuration so deploys don't change them. RETAIN means CDK never deletes
        # them, even if removed from this file or the stack is destroyed.

        raw_bucket = self.existing_bucket(
            "RawBucket",
            raw_bucket_name,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_PREFERRED,
        )

        web_bucket = self.existing_bucket(
            "WebBucket",
            web_bucket_name,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            website_index_document="chart.html",
            cors=[s3.CorsRule(allowed_methods=[s3.HttpMethods.GET], allowed_origins=["*"])],
        )

        table = dynamodb.Table(
            self,
            "Table",
            table_name=table_name,
            partition_key=dynamodb.Attribute(name="game_date", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            table_class=dynamodb.TableClass.STANDARD,
            deletion_protection=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Bucket policies (imported). Public reads of both buckets go through these, so they
        # are RETAINed like the buckets. Statements mirror the live policies; StarPrincipal
        # renders "*" exactly as the live policies have it.
        raw_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="Stmt1741400079772",
                principals=[
                    iam.ArnPrincipal(
                        self.format_arn(
                            service="iam",
                            region="",
                            resource="user",
                            resource_name=self.node.try_get_context("kol:bucketUserName"),
                        )
                    )
                ],
                actions=["s3:*"],
                resources=[raw_bucket.bucket_arn],
            )
        )
        for bucket, policy_id in (
            (raw_bucket, "Policy1741400083921"),
            (web_bucket, "kol-exchange-web-public-access-policy"),
        ):
            bucket.add_to_resource_policy(
                iam.PolicyStatement(
                    sid="PublicReadGetObject",
                    principals=[iam.StarPrincipal()],
                    actions=["s3:GetObject"],
                    resources=[bucket.arn_for_objects("*")],
                )
            )
            bucket.policy.apply_removal_policy(RemovalPolicy.RETAIN)
            # Policy "Id" labels from the live policies (iam.PolicyDocument has no Id field)
            bucket.policy.node.default_child.add_property_override(
                "PolicyDocument.Id", policy_id
            )

        # KoL credentials: JSON secret {"username": "...", "password": "..."} (imported).
        # L1 with no SecretString/GenerateSecretString so CloudFormation manages the secret
        # but never sets or regenerates its value; the value is set outside the template.
        kol_secret_resource = secretsmanager.CfnSecret(self, "KolSecret", name=secret_name)
        kol_secret_resource.apply_removal_policy(RemovalPolicy.RETAIN)
        kol_secret = secretsmanager.Secret.from_secret_complete_arn(
            self, "KolSecretRef", kol_secret_resource.ref
        )

        # ---- Functions (sizes match the existing hand-built Lambdas) ------------------------

        # Upload: Kolmafia container that fetches the rate and writes JSON to the raw bucket
        upload_fn = self.container_function(
            "UploadFunction",
            "kol-exchange-upload",
            {
                "BUCKET_NAME": raw_bucket.bucket_name,
                "KOL_SECRET_ID": kol_secret_resource.ref,
            },
        )
        raw_bucket.grant_put(upload_fn)
        kol_secret.grant_read(upload_fn)

        # Process: loads new data into DynamoDB, writes CSVs and graphs to the web bucket
        process_fn = self.container_function(
            "ProcessFunction",
            "kol-exchange-process",
            {
                "WEB_BUCKET_NAME": web_bucket.bucket_name,
                "TABLE_NAME": table.table_name,
            },
        )
        raw_bucket.grant_read(process_fn)
        web_bucket.grant_put(process_fn)
        table.grant_read_write_data(process_fn)

        # Data API: serves raw JSON by date
        api_fn = lambda_.Function(
            self,
            "ApiFunction",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset(
                str(REPO_ROOT / "kol-exchange-data-api"), exclude=["__pycache__"]
            ),
            memory_size=128,
            timeout=Duration.seconds(5),
            environment={"BUCKET_NAME": raw_bucket.bucket_name},
            log_group=self.log_group("ApiFunctionLogs"),
        )
        raw_bucket.grant_read(api_fn)

        # ---- HTTP API -----------------------------------------------------------------------
        # The existing API, its stage, route and integration are imported with `cdk import`
        # so clients keep the same execute-api URL (it is tied to the API ID and can never be
        # recreated). L1 constructs are used so every property mirrors the live configuration
        # exactly. RETAIN: deleting the API would permanently lose the URL.
        #
        # While kol:legacyApiFunctionName is set, the integration targets that hand-built
        # function (as it does today, so importing changes nothing). Clear it in cdk.json to
        # cut the API over to ApiFunction (not with -c: the next deploy without it would point
        # the API back at the old function).
        legacy_api_fn_name = self.node.try_get_context("kol:legacyApiFunctionName")

        http_api = apigw.CfnApi(
            self,
            "DataApi",
            name="kol-exchange-data-api-getrate",
            protocol_type="HTTP",
            route_selection_expression="$request.method $request.path",
            # api_key_selection_expression is reported by the live API but rejected on update
            # for HTTP APIs, so it must be left out
            disable_execute_api_endpoint=False,
            cors_configuration=apigw.CfnApi.CorsProperty(
                allow_credentials=False,
                allow_methods=["GET"],
                allow_origins=["*"],
                max_age=0,
            ),
        )

        api_stage = apigw.CfnStage(
            self,
            "DataApiDefaultStage",
            api_id=http_api.ref,
            stage_name="$default",
            auto_deploy=True,
            default_route_settings=apigw.CfnStage.RouteSettingsProperty(
                detailed_metrics_enabled=False
            ),
        )

        integration_target_arn = (
            self.format_arn(
                service="lambda",
                resource="function",
                resource_name=legacy_api_fn_name,
                arn_format=ArnFormat.COLON_RESOURCE_NAME,
            )
            if legacy_api_fn_name
            else api_fn.function_arn
        )

        api_integration = apigw.CfnIntegration(
            self,
            "DataApiIntegration",
            api_id=http_api.ref,
            integration_type="AWS_PROXY",
            integration_method="POST",
            integration_uri=integration_target_arn,
            connection_type="INTERNET",
            payload_format_version="2.0",
            timeout_in_millis=30000,
        )
        if not legacy_api_fn_name:
            # Must exist before the integration switches to the new function
            api_permission = lambda_.CfnPermission(
                self,
                "ApiInvokePermission",
                action="lambda:InvokeFunction",
                function_name=api_fn.function_arn,
                principal="apigateway.amazonaws.com",
                source_arn=self.format_arn(
                    service="execute-api",
                    resource=http_api.ref,
                    resource_name="*/*/getrate",
                ),
            )
            api_integration.add_resource_dependency(api_permission)

        api_route = apigw.CfnRoute(
            self,
            "DataApiGetRateRoute",
            api_id=http_api.ref,
            route_key="GET /getrate",
            authorization_type="NONE",
            api_key_required=False,
            target=f"integrations/{api_integration.ref}",
        )

        for resource in (http_api, api_stage, api_integration, api_route):
            resource.apply_removal_policy(RemovalPolicy.RETAIN)

        # ---- Triggers -----------------------------------------------------------------------
        # Off by default so this stack doesn't double-run alongside the existing
        # hand-built schedule and S3 trigger. Enable at cutover by setting kol:enableTriggers
        # to true in cdk.json (not with -c: the next deploy without it would remove the
        # schedule and all of the raw bucket's notifications). Note: because the raw bucket is
        # now CDK-managed, the S3 notification REPLACES the bucket's existing trigger to the
        # old process function.
        if enable_triggers:
            scheduler.Schedule(
                self,
                "DailyUpload",
                description="Daily KoL exchange rate fetch",
                schedule=scheduler.ScheduleExpression.expression(
                    f"cron({schedule_cron})", TimeZone.of(schedule_tz)
                ),
                target=scheduler_targets.LambdaInvoke(upload_fn, retry_attempts=0),
            )
            raw_bucket.add_event_notification(
                s3.EventType.OBJECT_CREATED,
                s3n.LambdaDestination(process_fn),
                s3.NotificationKeyFilter(suffix=".json"),
            )

        CfnOutput(self, "UploadFunctionName", value=upload_fn.function_name)
        CfnOutput(self, "ProcessFunctionName", value=process_fn.function_name)
        CfnOutput(self, "ApiFunctionName", value=api_fn.function_name)
        CfnOutput(self, "ApiUrl", value=f"{http_api.attr_api_endpoint}/getrate")

        tags = dict(APP_TAGS)
        if aws_application_arn:
            tags["awsApplication"] = aws_application_arn
        for child in self.node.children:
            for key, value in tags.items():
                Tags.of(child).add(key, value)
