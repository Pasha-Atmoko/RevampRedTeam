# infra/orchestration_stack.py
"""Step Functions Standard workflow + REST API (API key + CORS).

Flow: ValidateScope -> ProfileAndScenario -> ExecuteAttack -> Report
Any state failure is caught -> MarkFailed.
"""
from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct

API_KEY_VALUE = "tier2-demo-key-7h3x9q2"  # demo-grade; rotate / Secrets Manager for prod


class OrchestrationStack(Stack):
    def __init__(self, scope: Construct, cid: str, *, compute, **kwargs) -> None:
        super().__init__(scope, cid, **kwargs)

        mark_failed = tasks.LambdaInvoke(
            self, "MarkFailed", lambda_function=compute.failed_fn,
            payload_response_only=True)

        def state(label, fn, result_path="$"):
            t = tasks.LambdaInvoke(self, label, lambda_function=fn,
                                   payload_response_only=True, result_path=result_path)
            t.add_retry(errors=["States.TaskFailed"], max_attempts=2,
                        interval=Duration.seconds(3), backoff_rate=2.0)
            t.add_catch(mark_failed, errors=["States.ALL"], result_path="$.error")
            return t

        validate = state("ValidateScope", compute.validate_fn)
        profile = state("ProfileAndScenario", compute.profile_fn)
        execute = state("ExecuteAttack", compute.execute_fn)
        report = state("Report", compute.report_fn)

        definition = validate.next(profile).next(execute).next(report)
        self.state_machine = sfn.StateMachine(
            self, "Tier2StateMachine",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=Duration.minutes(30))

        compute.submit_fn.add_environment("STATE_MACHINE_ARN",
                                          self.state_machine.state_machine_arn)
        self.state_machine.grant_start_execution(compute.submit_fn)

        # REST API with API key + usage plan + CORS preflight.
        api = apigw.RestApi(
            self, "Tier2Api", rest_api_name="tier2",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["content-type", "x-api-key"]))

        scans = api.root.add_resource("scan")
        scans.add_method("POST", apigw.LambdaIntegration(compute.submit_fn),
                         api_key_required=True)
        one = scans.add_resource("{id}")
        one.add_method("GET", apigw.LambdaIntegration(compute.get_fn),
                       api_key_required=True)

        key = api.add_api_key("Tier2Key", value=API_KEY_VALUE)
        plan = api.add_usage_plan("Tier2Plan",
                                  throttle=apigw.ThrottleSettings(rate_limit=5,
                                                                  burst_limit=10))
        plan.add_api_key(key)
        plan.add_api_stage(stage=api.deployment_stage)

        CfnOutput(self, "ApiUrl", value=api.url)
        CfnOutput(self, "ApiKeyValue", value=API_KEY_VALUE)
