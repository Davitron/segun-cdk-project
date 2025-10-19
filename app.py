#!/usr/bin/env python3

import aws_cdk as cdk
from stacks.network.network_stack import NetworkStack

app = cdk.App()


env = cdk.Environment(
    account="737247133878",
    region="eu-west-1"
)

NetworkStack(app, "NetworkStack", 
    vpc_cidr="172.16.0.0/16",
    env=env
)

app.synth()
