import aws_cdk as cdk
from aws_cdk.assertions import Template
from stacks.network.network_stack import NetworkStack

def _cluster_tag_present(tags):
    return any(
        t.get("Value") == "shared" and (
            (
                isinstance(t.get("Key"), dict) and "Fn::Join" in t["Key"] and
                "kubernetes.io/cluster/" in "".join(
                    p if isinstance(p, str) else "" 
                    for p in t["Key"]["Fn::Join"][1]
                )
            )
        )
        for t in tags
    )
    
def _has_role_tag(tags, role_key):
    return any(t.get("Key") == role_key and t.get("Value") == "1" for t in tags)

def _subnet_type(tags):
    return next((t.get("Value") for t in tags if t.get("Key") == "aws-cdk:subnet-type"), None)

def synth_network_stack(vpc_cidr: str = "172.16.0.0/16"):
    app = cdk.App()
    stack = NetworkStack(app, "NetworkStackTest", 
                vpc_cidr=vpc_cidr,
                env=cdk.Environment(account="111111111111", region="eu-west-1")
    )
    template = Template.from_stack(stack)
    return stack, template


def test_vpc_exists_with_cidr():
    _, template = synth_network_stack()
    template.has_resource_properties("AWS::EC2::VPC", {
        "CidrBlock": "172.16.0.0/16"
    })


def test_has_expected_subnet_counts():
    stack, template = synth_network_stack()
    subnet_resources = [r for r, res in template.to_json().get("Resources", {}).items() if res["Type"] == "AWS::EC2::Subnet"]
    assert len(subnet_resources) == 6, f"Expected 9 subnets (3 of each type), found {len(subnet_resources)}"


def test_public_subnets_have_cluster_and_elb_tags():
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
    stack, template = synth_network_stack()
    azs_used = set()
    subnet_resources = template.find_resources("AWS::EC2::Subnet")
    for res in subnet_resources.values():
        az = res["Properties"].get("AvailabilityZone")
        if az:
            azs_used.add(az)
    assert len(azs_used) == 3, f"Expected subnets to be distributed across 3 AZs, found {len(azs_used)}"


def test_igw_created():
    _, template = synth_network_stack()
    template.has_resource("AWS::EC2::InternetGateway", {})

def test_single_nat_gateway_created():
    _, template = synth_network_stack()
    nat_gateways = [
        res for res in template.to_json().get("Resources", {}).values()
        if res["Type"] == "AWS::EC2::NatGateway"
    ]
    assert len(nat_gateways) == 1, f"Expected 1 NAT Gateway, found {len(nat_gateways)}"
    
def test_route_tables_created():
    _, template = synth_network_stack()
    route_tables = [
        res for res in template.to_json().get("Resources", {}).values()
        if res["Type"] == "AWS::EC2::RouteTable"
    ]
    assert len(route_tables) == 6, f"Expected 6 Route Tables (3 per subnet type), found {len(route_tables)}"

