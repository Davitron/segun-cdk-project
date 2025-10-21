from constructs import Construct
from aws_cdk import (
    Stack,
    aws_eks as eks,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_ssm as ssm,
    CfnOutput,
    Tags
)
from aws_cdk.lambda_layer_kubectl_v33 import KubectlV33Layer



class ClusterStack(Stack):

    def __init__(self, scope: Construct, id: str, vpc: ec2.IVpc = None, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Use context for cluster name to ensure a plain string (run with: cdk deploy -c clusterName=SwisscomCluster)
        cluster_name_str = self.node.try_get_context("clusterName") or "SwisscomCluster"
        cluster_env_context = self.node.try_get_context("environment") or "development"
        
        # Create EKS Cluster Service Role
        cluster_role = iam.Role(self, "ClusterServiceRole",
            assumed_by=iam.ServicePrincipal("eks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSClusterPolicy")
            ]
        )


        ssm.StringParameter(self, "ClusterEnvParameter",
            parameter_name="/platform/account/env",
            string_value=cluster_env_context
        )

        self.cluster = eks.Cluster(
            self,
            "SwisscomEKSCluster",
            cluster_name=cluster_name_str,
            version=eks.KubernetesVersion.V1_33,
            kubectl_layer=KubectlV33Layer(self, "Kubectl"),
            role=cluster_role,
            vpc=vpc,
            vpc_subnets=[
                ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
            ],
            default_capacity=0,
            endpoint_access=eks.EndpointAccess.PUBLIC_AND_PRIVATE,
            authentication_mode=eks.AuthenticationMode.API_AND_CONFIG_MAP,
            bootstrap_cluster_creator_admin_permissions=True,
            cluster_logging=[
                eks.ClusterLoggingTypes.API,
                eks.ClusterLoggingTypes.AUDIT,
                eks.ClusterLoggingTypes.AUTHENTICATOR,
            ]
        )
        
        # Use ArnPrincipal for access entry instead of a raw string for clarity
        self.access_entry = eks.AccessEntry(
            self,
            "ClusterAdminAccessEntry",
            cluster=self.cluster,
            principal=f"arn:aws:iam::{self.account}:user/segun-manager",
            access_policies=[
                eks.AccessPolicy(
                    policy=eks.AccessPolicyArn.AMAZON_EKS_CLUSTER_ADMIN_POLICY,
                    access_scope=eks.AccessScope(type=eks.AccessScopeType.CLUSTER),
                )
            ],
        )
        
        self.add_managed_node_group()
        self.resource_tags()

        CfnOutput(self, "ClusterNameOutput", value=self.cluster.cluster_name)
        CfnOutput(self, "ClusterEndpointOutput", value=self.cluster.cluster_endpoint)
        CfnOutput(self, "ClusterArnOutput", value=self.cluster.cluster_arn)
        CfnOutput(
            self,
            "KubeconfigUpdateCommand",
            value=f"aws eks update-kubeconfig --name {self.cluster.cluster_name} --region {self.region}",
            description="Run this command locally to configure kubectl access",
        )

    def add_managed_node_group(self):
        """Add EKS managed node group"""
        # Create IAM role for node group
        node_group_role = iam.Role(self, "NodeGroupRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSWorkerNodePolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKS_CNI_Policy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryReadOnly")
            ]
        )
        
        self.node_group = self.cluster.add_nodegroup_capacity(
            "WorkerNodes",
            nodegroup_name="Default",
            instance_types=[
                ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MEDIUM),
            ],
            min_size=2,
            max_size=5,
            desired_size=2,
            ami_type=eks.NodegroupAmiType.BOTTLEROCKET_X86_64,
            capacity_type=eks.CapacityType.ON_DEMAND,
            disk_size=20,
            node_role=node_group_role,
            tags={
                "Name": "SwisscomEKS-WorkerNode",
                "NodeGroup": "Default"
            }
        )

    def resource_tags(self):
        """Apply resource tags"""
        Tags.of(self).add("Project", "SwisscomAssessment")
        Tags.of(self).add("Environment", "Production")
        Tags.of(self.cluster).add("ClusterType", "EKS")
        Tags.of(self.cluster).add("ManagedBy", "CDK")

        
        