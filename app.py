#!/usr/bin/env python3
"""CDK app entry point for Tier2."""
import aws_cdk as cdk

from infra.network_stack import NetworkStack
from infra.data_stack import DataStack
from infra.compute_stack import ComputeStack
from infra.orchestration_stack import OrchestrationStack

app = cdk.App()
env = cdk.Environment()

network = NetworkStack(app, "Tier2-Network", env=env)
data = DataStack(app, "Tier2-Data", env=env)
compute = ComputeStack(app, "Tier2-Compute", vpc=network.vpc,
                       egress_sg=network.egress_sg, scans_table=data.scans_table,
                       report_bucket=data.report_bucket, scope_param=data.scope_param,
                       env=env)
OrchestrationStack(app, "Tier2-Orchestration", compute=compute, env=env)
app.synth()
