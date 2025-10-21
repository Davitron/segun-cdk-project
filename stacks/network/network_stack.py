"""Network stack module.

Defines the VPC infrastructure with multi-AZ subnets for the EKS platform:
- Public subnets for load balancers (tagged for kubernetes.io/role/elb)
- Private subnets with egress for worker nodes (tagged for kubernetes.io/role/internal-elb)
- Kubernetes cluster discovery tags (kubernetes.io/cluster/<VpcName>=shared)
"""

from constructs import Construct
from aws_cdk import (
    CfnParameter,
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
            vpc_cidr: str = "172.16.0.0/16",
            **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.vpc_name_param = CfnParameter(self, "VpcName",
            type="String",
            description="The name of the VPC",
            default="SwisscomVPC"
        ).value_as_string

        self.vpc = ec2.Vpc(self, "SwisscomVPC",
            ip_addresses=ec2.IpAddresses.cidr(vpc_cidr),
            max_azs=3,
            enable_dns_hostnames=True,
            enable_dns_support=True,
            vpc_name=self.vpc_name_param,
            nat_gateways=1,
            nat_gateway_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC
            ),
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                    map_public_ip_on_launch=True
                ),
                ec2.SubnetConfiguration(
                    name="Workers",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=20
                )
            ],
        )

        self.resource_tags()

        CfnOutput(self, "VpcId", value=self.vpc.vpc_id)
        CfnOutput(self, "AvailabilityZones", value=",".join(self.vpc.availability_zones))
        CfnOutput(self, "PublicSubnetCount", value=str(len(self.vpc.public_subnets)))
        CfnOutput(self, "PrivateSubnetCount", value=str(len(self.vpc.private_subnets)))
        CfnOutput(self, "IsolatedSubnetCount", value=str(len(self.vpc.isolated_subnets)))
        CfnOutput(self,
            "PrivateSubnetIds",
            value=",".join([subnet.subnet_id for subnet in self.vpc.private_subnets])
        )

    def resource_tags(self):
        """Tag subnets with meaningful names"""
        # Tag subnets with meaningful names
        for subnet in self.vpc.public_subnets:
            az_index = self.vpc.availability_zones.index(subnet.availability_zone)
            az_letter = chr(ord('A') + az_index)  # Convert index to letter (0 -> A, 1 -> B, etc.)
            Tags.of(subnet).add("Name", f"{self.vpc_name_param}-Public-{az_letter}")
            Tags.of(subnet).add(f"kubernetes.io/cluster/{self.vpc_name_param}", "shared")
            Tags.of(subnet).add("kubernetes.io/role/elb", "1")

        for subnet in self.vpc.private_subnets:
            az_index = self.vpc.availability_zones.index(subnet.availability_zone)
            az_letter = chr(ord('A') + az_index)
            Tags.of(subnet).add("Name", f"{self.vpc_name_param}-Workers-{az_letter}")
            Tags.of(subnet).add(f"kubernetes.io/cluster/{self.vpc_name_param}", "shared")
            Tags.of(subnet).add("kubernetes.io/role/internal-elb", "1")
