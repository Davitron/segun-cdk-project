import aws_cdk as cdk
from aws_cdk.assertions import Template, Capture, Match
from aws_cdk import aws_ec2 as ec2, aws_eks as eks
from stacks.network.network_stack import NetworkStack
from stacks.cluster.cluster_stacks import ClusterStack
from stacks.platform.nginx_ingress_stack import NginxIngressStack


def synth_platform_stack():
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
    _, template = synth_platform_stack()
    template.has_resource_properties("AWS::Lambda::Function", {
        "Handler": "handler.on_event"
    })


def test_custom_resource_exists():
    _, template = synth_platform_stack()
    template.has_resource("AWS::CloudFormation::CustomResource", {})


def test_helm_chart_exists():
    _, template = synth_platform_stack()
    # HelmChart is synthesized as a Custom::AWS resource. Check presence with release name in properties
    template.has_resource_properties("Custom::AWSCDK-EKS-HelmChart", {
        "Release": "nginx-ingress",
        "CreateNamespace": True
    })
