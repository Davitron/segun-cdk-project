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


env_name = app.node.try_get_context("environment") or "dev"
env_context = app.node.try_get_context(env_name)
if not env_context:
    raise ValueError(f"No context found for environment '{env_name}'. Available environments: dev, stg, prod")

service_name = app.node.try_get_context("service_name")
if not service_name:
    raise ValueError("No 'service_name' found in context")

env = cdk.Environment(
    account=env_context["account_id"],
    region=env_context["region"]
)

print(f"Synthesizing stacks for environment: {env_name} (Account: {env.account}, Region: {env.region})")

# Create network stack
network_stack = NetworkStack(app, "NetworkStack",
    service_name=service_name,
    vpc_cidr=env_context["vpc_cidr"],
    env=env
)

# Create cluster stack that depends on network stack
cluster_stack = ClusterStack(app, "ClusterStack",
    service_name=service_name,
    environment_name=env_context["env"],
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
