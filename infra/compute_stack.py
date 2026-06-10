# infra/compute_stack.py
"""Lambda functions + shared dependency layer for Tier2.

Build the layer locally before synth:
  pip install -r backend/requirements-lambda.txt -t build/layer/python
"""
from aws_cdk import Duration, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct


class ComputeStack(Stack):
    def __init__(self, scope: Construct, cid: str, *, vpc, egress_sg,
                 scans_table, report_bucket, scope_param, **kwargs) -> None:
        super().__init__(scope, cid, **kwargs)

        layer = lambda_.LayerVersion(
            self, "DepsLayer", code=lambda_.Code.from_asset("build/layer"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="httpx, boto3")
        code = lambda_.Code.from_asset("backend/src")
        common_env = {"SCANS_TABLE": scans_table.table_name,
                      "REPORT_BUCKET": report_bucket.bucket_name,
                      "SCOPE_PARAM_NAME": scope_param.parameter_name}

        def fn(name, handler, *, in_vpc=False, timeout=300, memory=256):
            return lambda_.Function(
                self, name, runtime=lambda_.Runtime.PYTHON_3_12, handler=handler,
                code=code, layers=[layer], timeout=Duration.seconds(timeout),
                memory_size=memory, environment=common_env,
                vpc=vpc if in_vpc else None,
                vpc_subnets=ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS) if in_vpc else None,
                security_groups=[egress_sg] if in_vpc else None)

        self.get_fn = fn("GetScan", "lambdas.get_scan.handler", timeout=30)
        self.validate_fn = fn("ValidateScope", "lambdas.validate_scope.handler")
        self.profile_fn = fn("ProfileAndScenario",
                             "lambdas.profile_and_scenario.handler",
                             timeout=120, memory=512)
        self.execute_fn = fn("ExecuteAttack", "lambdas.execute_attack.handler",
                             in_vpc=True, timeout=900, memory=512)
        self.report_fn = fn("Report", "lambdas.report.handler")
        self.failed_fn = fn("MarkFailed", "lambdas.mark_failed.handler", timeout=30)

        # Expose common_env and helpers for OrchestrationStack to create submit_fn.
        self.code = code
        self.layer = layer
        self.common_env = common_env
        self.vpc = vpc
        self.egress_sg = egress_sg
        self.scans_table = scans_table

        # Least-privilege grants.
        for f in (self.get_fn, self.validate_fn, self.profile_fn,
                  self.execute_fn, self.report_fn, self.failed_fn):
            scans_table.grant_read_write_data(f)
        for f in (self.validate_fn, self.execute_fn):
            scope_param.grant_read(f)
        report_bucket.grant_put(self.report_fn)

        bedrock_policy = iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:Converse"], resources=["*"])
        for f in (self.profile_fn, self.execute_fn):
            f.add_to_role_policy(bedrock_policy)
