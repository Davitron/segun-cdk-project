#!/usr/bin/env python3
"""CDK application entrypoint.

Defines and synthesizes the infrastructure stacks for the platform:
1. NetworkStack: VPC and subnet tagging for EKS / ELB discovery.
2. ClusterStack: EKS cluster (v1.33), managed node group, access configuration.
3. NginxIngressStack: Ingress controller Helm chart with dynamic replica custom resource.
"""

import aws_cdk as cdk
from stacks.network.network_stack import NetworkStack
from stacks.cluster.cluster_stacks import ClusterStack
from stacks.platform.nginx_ingress_stack import NginxIngressStack

app = cdk.App()

env = cdk.Environment(
    account="737247133878",
    region="eu-west-1"
)

# Create network stack
network_stack = NetworkStack(app, "NetworkStack",
    vpc_cidr="172.16.0.0/16",
    env=env
)

# Create cluster stack that depends on network stack
cluster_stack = ClusterStack(app, "ClusterStack",
    vpc=network_stack.vpc,
    env=env
)

# Create Nginx Ingress stack
nginx_ingress_stack = NginxIngressStack(app, "NginxIngressStack",
    cluster=cluster_stack.cluster,
    env=env
)

# Add dependency
cluster_stack.add_dependency(network_stack)
nginx_ingress_stack.add_dependency(cluster_stack)

app.synth()
