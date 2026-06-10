# infra/network_stack.py
"""VPC + NAT for controlled egress to external targets."""
from aws_cdk import Stack
from aws_cdk import aws_ec2 as ec2
from constructs import Construct


class NetworkStack(Stack):
    def __init__(self, scope: Construct, cid: str, **kwargs) -> None:
        super().__init__(scope, cid, **kwargs)
        self.vpc = ec2.Vpc(
            self, "Tier2Vpc", max_azs=2, nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="public",
                    subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=24)])
        self.egress_sg = ec2.SecurityGroup(
            self, "EgressSg", vpc=self.vpc, allow_all_outbound=False,
            description="Tier2 egress - restrict to authorized target ports")
        for port in (80, 443, 8080):
            self.egress_sg.add_egress_rule(
                ec2.Peer.any_ipv4(), ec2.Port.tcp(port), f"target port {port}")
