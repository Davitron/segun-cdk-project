"""Unit tests for ClusterStack EKS cluster and node group resources.

Tests EKS cluster creation (v1.33), node group configuration (Bottlerocket AMI,
scaling config), SSM parameter creation, and CloudFormation outputs. Validates
that cluster resources are correctly synthesized with proper dependencies on VPC.
"""

import aws_cdk as cdk
from aws_cdk.assertions import Template, Capture
from stacks.cluster.cluster_stacks import ClusterStack
from stacks.network.network_stack import NetworkStack


def synth_cluster_stack(vpc_cidr: str = "172.16.0.0/16"):
    """Synthesize cluster stack with network dependency for testing.

    Args:
        vpc_cidr: CIDR block for the test VPC (default: 172.16.0.0/16).

    Returns:
        Tuple of (cluster_stack, template) for assertions.
    """
    app = cdk.App()
    env = cdk.Environment(account="111111111111", region="eu-west-1")
    network_stack = NetworkStack(app, "NetworkStackTest", env=env)
    cluster_stack = ClusterStack(app, "ClusterStackTest", vpc=network_stack.vpc, env=env)
    cluster_stack.add_dependency(network_stack)
    template = Template.from_stack(cluster_stack)
    return cluster_stack, template


def test_cluster_resource_exists():
    """Test EKS cluster custom resource is created."""
    _, template = synth_cluster_stack()
    template.has_resource("Custom::AWSCDK-EKS-Cluster", {})

def test_cluster_name_and_version():
    """Test cluster has correct name prefix and Kubernetes version 1.33."""
    _, template = synth_cluster_stack()
    capture_cluster_config = Capture()
    template.has_resource_properties("Custom::AWSCDK-EKS-Cluster", {
        "Config": capture_cluster_config
    })

    cluster_config_as_dict = capture_cluster_config.as_object()
    assert cluster_config_as_dict.get("name", "").startswith("SwisscomCluster"), "Cluster name does not match expected value"
    assert cluster_config_as_dict.get("version") == "1.33", "Cluster version does not match expected value"


def test_nodegroup_resource_exists():
    """Test EKS managed node group resource is created."""
    _, template = synth_cluster_stack()
    template.has_resource("AWS::EKS::Nodegroup", {})


def test_nodegroup_config():
    """Test node group has correct AMI type, scaling config, and subnet distribution."""
    _, template = synth_cluster_stack()
    capture_cluster_subnet = Capture()
    template.has_resource_properties("AWS::EKS::Nodegroup", {
        "AmiType": "BOTTLEROCKET_x86_64",
        "ScalingConfig": {
            "DesiredSize": 2,
            "MinSize": 2,
            "MaxSize": 5
        },
        "Subnets": capture_cluster_subnet
    })
    subnet_ids = capture_cluster_subnet.as_array()
    assert len(subnet_ids) == 3, f"Expected 3 subnets for node group, found {len(subnet_ids)}"

def test_ssm_env_parameter_created():
    """Test SSM parameter for environment configuration is created."""
    _, template = synth_cluster_stack()
    template.has_resource_properties("AWS::SSM::Parameter", {
        "Name": "/platform/account/env",
        "Type": "String"
    })


def test_cluster_outputs_present():
    """Test cluster name and endpoint outputs are present in CloudFormation template."""
    stack, template = synth_cluster_stack()
    outputs = stack.node.try_find_child("ClusterNameOutput"), stack.node.try_find_child("ClusterEndpointOutput")
    for construct in outputs:
        assert construct is not None, "Missing expected cluster output construct"
    tpl_json = template.to_json()
    cfn_outputs = tpl_json.get("Outputs", {})
    assert "ClusterNameOutput" in cfn_outputs, "ClusterNameOutput missing in template outputs"
    assert "ClusterEndpointOutput" in cfn_outputs, "ClusterEndpointOutput missing in template outputs"
