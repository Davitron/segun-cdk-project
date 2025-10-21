"""Unit tests for NginxIngressStack platform resources.

Tests the nginx ingress controller Helm deployment including Lambda function,
custom resource provider, and Helm chart configuration. Validates that all
platform resources are correctly synthesized with proper dependencies.
"""

import aws_cdk as cdk
from aws_cdk.assertions import Template

from stacks.network.network_stack import NetworkStack
from stacks.cluster.cluster_stacks import ClusterStack
from stacks.platform.nginx_ingress_stack import NginxIngressStack


def synth_platform_stack():
    """Synthesize platform stack with network and cluster dependencies for testing."""
    app = cdk.App()
    env = cdk.Environment(account="111111111111", region="eu-west-1")
    network_stack = NetworkStack(app, "NetworkStackTest", env=env)
    cluster_stack = ClusterStack(app, "ClusterStackTest", vpc=network_stack.vpc, env=env)
    nginx_ingress_stack = NginxIngressStack(app, "NginxIngressStackTest", cluster=cluster_stack.cluster, env=env)
    cluster_stack.add_dependency(network_stack)
    nginx_ingress_stack.add_dependency(cluster_stack)
    template = Template.from_stack(nginx_ingress_stack)
    return nginx_ingress_stack, template


def test_lambda_function_exists():
    """Test Lambda function for replica count custom resource is created."""
    _, template = synth_platform_stack()
    template.has_resource_properties("AWS::Lambda::Function", {
        "Handler": "handler.on_event"
    })


def test_custom_resource_exists():
    """Test custom resource is created for dynamic replica count retrieval."""
    _, template = synth_platform_stack()
    template.has_resource("AWS::CloudFormation::CustomResource", {})


def test_helm_chart_exists():
    """Test Helm chart resource for nginx-ingress is created with correct release name."""
    _, template = synth_platform_stack()
    # HelmChart is synthesized as a Custom::AWS resource. Check presence with release name in properties
    template.has_resource_properties("Custom::AWSCDK-EKS-HelmChart", {
        "Release": "nginx-ingress",
        "CreateNamespace": True
    })
