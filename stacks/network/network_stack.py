"""Network stack module.

Defines the VPC infrastructure with multi-AZ subnets for the EKS platform:
- Public subnets for load balancers (tagged for kubernetes.io/role/elb)
- Private subnets with egress for worker nodes (tagged for kubernetes.io/role/internal-elb)
- Kubernetes cluster discovery tags (kubernetes.io/cluster/<VpcName>=shared)
"""
import ipaddress
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    CfnOutput,
    Tags
)


class NetworkStack(Stack):
    """CDK Stack for VPC and networking resources.

    Creates a multi-AZ VPC with public and private subnets, tagging subnets
    for Kubernetes ELB discovery
    """

    def __init__(self, scope: Construct,
            construct_id: str,
            service_name: str,
            vpc_cidr: str,
            **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vpc_name = f"{service_name}-vpc"
        self.vpc_cidr = vpc_cidr

        try:
            ipaddress.ip_network(self.vpc_cidr)
        except ValueError as e:
            raise ValueError(f"Invalid VPC CIDR block: {self.vpc_cidr}") from e

        self.vpc = ec2.Vpc(self, "SwisscomVPC",
            ip_addresses=ec2.IpAddresses.cidr(self.vpc_cidr),
            max_azs=3,
            enable_dns_hostnames=True,
            enable_dns_support=True,
            vpc_name=self.vpc_name,
            nat_gateways=1,
            nat_gateway_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC
            ),
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                    map_public_ip_on_launch=True
                ),
                ec2.SubnetConfiguration(
                    name="workers",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=20
                )
            ],
        )

        self.resource_tags(service_name)

        CfnOutput(self, "VpcId", value=self.vpc.vpc_id)
        CfnOutput(self, "AvailabilityZones", value=",".join(self.vpc.availability_zones))
        CfnOutput(self, "PublicSubnetCount", value=str(len(self.vpc.public_subnets)))
        CfnOutput(self, "PrivateSubnetCount", value=str(len(self.vpc.private_subnets)))
        CfnOutput(self, "IsolatedSubnetCount", value=str(len(self.vpc.isolated_subnets)))
        CfnOutput(self,
            "PrivateSubnetIds",
            value=",".join([subnet.subnet_id for subnet in self.vpc.private_subnets])
        )

    def resource_tags(self, service_name: str) -> None:
        """Tag subnets with meaningful names"""
        # Tag subnets with meaningful names
        for subnet in self.vpc.public_subnets:
            az_index = self.vpc.availability_zones.index(subnet.availability_zone)
            az_letter = chr(ord('a') + az_index)
            Tags.of(subnet).add("Name", f"{service_name}-public-{az_letter}")
            Tags.of(subnet).add(f"kubernetes.io/cluster/{service_name}", "shared")
            Tags.of(subnet).add("kubernetes.io/role/elb", "1")

        for subnet in self.vpc.private_subnets:
            az_index = self.vpc.availability_zones.index(subnet.availability_zone)
            az_letter = chr(ord('a') + az_index)
            Tags.of(subnet).add("Name", f"{service_name}-workers-{az_letter}")
            Tags.of(subnet).add(f"kubernetes.io/cluster/{service_name}", "shared")
            Tags.of(subnet).add("kubernetes.io/role/internal-elb", "1")
