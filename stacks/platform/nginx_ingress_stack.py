from constructs import Construct
from aws_cdk import (
    Stack,
    Duration,
    aws_eks as eks,
    aws_lambda as _lambda,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_logs as logs,
    custom_resources as cr,
    Token,
    CustomResource,
)
import os


class NginxIngressStack(Stack):
    def __init__(self, scope: Construct, id: str, *, 
                 cluster: eks.Cluster,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        
        self.deploy_ingress_controller(cluster)

    def deploy_ingress_controller(self, cluster: eks.Cluster):
        lambda_role = iam.Role(
            self,
            "NginxReplicaLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMReadOnlyAccess")
            ]
        )


        lambda_path = os.path.join(os.path.dirname(__file__), '../../assets/_lambda')
        lambda_fn = _lambda.Function(self, "NginxReplicaLambda",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="handler.on_event",
            code=_lambda.Code.from_asset(lambda_path),
            timeout=Duration.seconds(300),
            role=lambda_role,
            log_retention=logs.RetentionDays.ONE_WEEK,
            environment={
                "ENVIRONMENT": "/platform/account/env"
            }
        )

        provider = cr.Provider(self, "NginxIngressReplicaProvider",
            on_event_handler=lambda_fn
        )
        replica_resource = CustomResource(
            self,
            "NginxIngressReplicaCustomResource",
            service_token=provider.service_token
        )

        replica_count_token = Token.as_number(replica_resource.get_att("ReplicaCount"))

        eks.HelmChart(
            self,
            "NginxIngressHelmChart",
            cluster=cluster,
            chart="ingress-nginx",
            repository="https://kubernetes.github.io/ingress-nginx",
            namespace="ingress-nginx",
            release="nginx-ingress",
            values={
                "fullnameOverride": "nginx-ingress",
                "nameOverride": "nginx-ingress",
                "controller": {
                    "replicaCount": replica_count_token,
                    "service": {"type": "LoadBalancer"},
                    "progressDeadlineSeconds": 600,
                    "minReadySeconds": 10
                }
            }
        )