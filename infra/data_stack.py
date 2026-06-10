# infra/data_stack.py
"""Stateful resources: scans table, reports bucket, scope allowlist parameter."""
from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as ddb
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_ssm as ssm
from constructs import Construct


class DataStack(Stack):
    def __init__(self, scope: Construct, cid: str, **kwargs) -> None:
        super().__init__(scope, cid, **kwargs)
        self.scans_table = ddb.Table(
            self, "Scans",
            partition_key=ddb.Attribute(name="pk", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="sk", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY)
        self.report_bucket = s3.Bucket(
            self, "Reports",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED, enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY, auto_delete_objects=True)
        # Fail-closed: seed with a non-routable placeholder; operator sets real scope.
        self.scope_param = ssm.StringListParameter(
            self, "ScopeAllowlist", parameter_name="/tier2/scope-allowlist",
            string_list_value=["127.0.0.1"])
