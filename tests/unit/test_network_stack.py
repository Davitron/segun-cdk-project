"""Unit tests for NetworkStack VPC and subnet configuration.

Tests VPC creation, subnet counts, Kubernetes/ELB tagging, AZ distribution,
NAT/IGW presence, and route tables. Validates that subnets are properly tagged
for EKS cluster discovery and load balancer provisioning.
"""
import ipaddress
import pytest
import aws_cdk as cdk
from aws_cdk.assertions import Template
from stacks.network.network_stack import NetworkStack

def _cluster_tag_present(tags):
    """Check if Kubernetes cluster discovery tag is present in subnet tags."""
    return any(
        t.get("Value") == "shared" and
            (isinstance(t.get("Key"), str) and t.get("Key").startswith("kubernetes.io/cluster/"))
        for t in tags
    )

def _has_role_tag(tags, role_key):
    """Check if subnet has the specified Kubernetes role tag (elb or internal-elb)."""
    return any(t.get("Key") == role_key and t.get("Value") == "1" for t in tags)

def _subnet_type(tags):
    """Extract subnet type (Public/Private) from CDK subnet tags."""
    return next((t.get("Value") for t in tags if t.get("Key") == "aws-cdk:subnet-type"), None)

def synth_network_stack(vpc_cidr: str = "172.16.0.0/16"):
    """Synthesize a NetworkStack for testing with the specified VPC CIDR."""
    app = cdk.App()
    env = cdk.Environment(account="111111111111", region="eu-west-1")
    stack = NetworkStack(app, "NetworkStackTest",
        service_name="test-service",
        vpc_cidr=vpc_cidr,
        env=env
    )
    template = Template.from_stack(stack)
    return stack, template


def test_vpc_exists_with_cidr():
    """Test VPC resource is created with expected CIDR block."""
    _, template = synth_network_stack()
    template.has_resource_properties("AWS::EC2::VPC", {
        "CidrBlock": "172.16.0.0/16"
    })


def test_has_expected_subnet_counts():
    """Test correct number of subnets are created (3 public + 3 private)."""
    _, template = synth_network_stack()
    subnet_resources = [r for r, res in template.to_json().get("Resources", {}).items() if res["Type"] == "AWS::EC2::Subnet"]
    assert len(subnet_resources) == 6, f"Expected 6 subnets (3 of each type), found {len(subnet_resources)}"


def test_public_subnets_have_cluster_and_elb_tags():
    """Test public subnets are tagged for Kubernetes cluster discovery and ELB."""
    _, template = synth_network_stack()
    public_subnets = template.find_resources("AWS::EC2::Subnet")
    matching = [
        res for res in public_subnets.values()
        if _subnet_type(res["Properties"].get("Tags", [])) == "Public"
           and _cluster_tag_present(res["Properties"].get("Tags", []))
           and _has_role_tag(res["Properties"].get("Tags", []), "kubernetes.io/role/elb")
    ]
    assert len(matching) == 3, f"Expected 3 public subnets fully tagged, found {len(matching)}"

def test_private_subnets_have_cluster_and_internal_elb_tags():
    """Test private subnets are tagged for Kubernetes cluster discovery and internal ELB."""
    _, template = synth_network_stack()
    private_subnets = template.find_resources("AWS::EC2::Subnet")
    matching = [
        res for res in private_subnets.values()
        if _subnet_type(res["Properties"].get("Tags", [])) == "Private"
           and _cluster_tag_present(res["Properties"].get("Tags", []))
           and _has_role_tag(res["Properties"].get("Tags", []), "kubernetes.io/role/internal-elb")
    ]
    assert len(matching) == 3, f"Expected 3 private subnets fully tagged, found {len(matching)}"


def test_az_distribution():
    """Test subnets are distributed across 3 availability zones."""
    _, template = synth_network_stack()
    azs_used = set()
    subnet_resources = template.find_resources("AWS::EC2::Subnet")
    for res in subnet_resources.values():
        az = res["Properties"].get("AvailabilityZone")
        if az:
            azs_used.add(az)
    assert len(azs_used) == 3, f"Expected subnets to be distributed across 3 AZs, found {len(azs_used)}"


def test_igw_created():
    """Test Internet Gateway is created for public subnet connectivity."""
    _, template = synth_network_stack()
    template.has_resource("AWS::EC2::InternetGateway", {})

def test_single_nat_gateway_created():
    """Test exactly one NAT Gateway is created for private subnet egress."""
    _, template = synth_network_stack()
    nat_gateways = [
        res for res in template.to_json().get("Resources", {}).values()
        if res["Type"] == "AWS::EC2::NatGateway"
    ]
    assert len(nat_gateways) == 1, f"Expected 1 NAT Gateway, found {len(nat_gateways)}"

def test_route_tables_created():
    """Test correct number of route tables are created for subnet routing."""
    _, template = synth_network_stack()
    route_tables = [
        res for res in template.to_json().get("Resources", {}).values()
        if res["Type"] == "AWS::EC2::RouteTable"
    ]
    assert len(route_tables) == 6, f"Expected 6 Route Tables (3 per subnet type), found {len(route_tables)}"


def test_valid_cidr_formats():
    """Test VPC accepts valid CIDR format strings."""
    valid_cidrs = [
        "10.0.0.0/16",
        "172.16.0.0/16", 
        "192.168.0.0/16"
    ]
    for cidr in valid_cidrs:
        ipaddress.ip_network(cidr)
        _, template = synth_network_stack(vpc_cidr=cidr)
        template.has_resource_properties("AWS::EC2::VPC", {
            "CidrBlock": cidr
        })


def test_invalid_vpc_cidr():
    """Test NetworkStack rejects invalid VPC CIDR formats."""
    invalid_cidrs = [
        "10.0.0.0",           # Missing subnet mask
        "10.0.0.0/",          # Empty subnet mask
        "10.0.0.0/33",        # Invalid subnet mask (>32)
        "256.0.0.0/16",       # Invalid IP (256 > 255)
        "10.0.0.0/-1",        # Negative subnet mask
        "not-an-ip/16",       # Non-IP string
        "",                   # Empty string
        "10.0.0.0/abc",       # Non-numeric subnet mask
        "10.0.0.256/16",      # Invalid IP octet
        "10.0.0.0/16/24"      # Multiple slashes
    ]
    for invalid_cidr in invalid_cidrs:
        with pytest.raises((ValueError, Exception)) as exc_info:
            synth_network_stack(vpc_cidr=invalid_cidr)
        assert exc_info.value is not None, f"Expected error for invalid CIDR: {invalid_cidr}"
