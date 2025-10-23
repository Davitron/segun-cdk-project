"""Lambda handler for nginx ingress replica count custom resource.

Determines the number of nginx ingress controller replicas based on environment
parameter stored in SSM. Maps environment values to replica counts:
- development: 1 replica
- staging/production: 2 replicas
- fallback (on errors): 1 replica (development)

Handles CloudFormation custom resource events (Create/Update/Delete) and returns
the computed replica count via the Data.ReplicaCount attribute.
"""

import os
import traceback
import boto3
from botocore.exceptions import ClientError

ssm = boto3.client("ssm")

def _replicas_from_env(env_value: str) -> int:
    """Map environment value to nginx ingress replica count.

    Args:
        env_value: Environment name (development, staging, production).

    Returns:
        Replica count: 1 for development, 2 for staging/production, 1 as fallback.
    """
    env_value = (env_value or "").strip().lower()
    if env_value == "development":
        return 1
    if env_value in ('staging', 'production'):
        return 2
    return 1  # default fallback

def _get_env_value(param_name: str) -> str:
    """Retrieve environment value from SSM parameter with error handling.

    Args:
        param_name: SSM parameter name to retrieve.

    Returns:
        Parameter value from SSM, or "development" if parameter not found or on error.
    """
    try:
        response = ssm.get_parameter(Name=param_name)
        return response["Parameter"]["Value"]
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "ParameterNotFound":
            print(f"Parameter {param_name} not found; falling back to development")
            return "development"
        print(f"ClientError retrieving {param_name}: {error_code}. Fallback to development")
        return "development"
    except Exception:
        print("Unexpected exception retrieving", param_name, traceback.format_exc())
        return "development"

def on_event(event, context):
    """CloudFormation custom resource handler for replica count computation.

    Args:
        event: CloudFormation custom resource event (Create/Update/Delete).
        context: Lambda context (unused but required by Lambda signature).

    Returns:
        Custom resource response with Data.ReplicaCount and optionally Data.EnvironmentValue.

    Raises:
        RuntimeError: If ENVIRONMENT environment variable is not set.
    """
    request_type = event.get("RequestType", "Create")
    param_name = os.environ.get("ENVIRONMENT")

    if not param_name:
        raise RuntimeError("ENVIRONMENT environment variable is required")

    # For Delete, return a stable physical id and a safe default
    if request_type == "Delete":
        return {
            "Data": {"ReplicaCount": 1},
        }

    # For Create/Update fetch environment and map to replica count
    env_value = _get_env_value(param_name)
    replica_count = _replicas_from_env(env_value)

    # Return numeric value (CloudFormation will treat it as a primitive via get_att)
    return {
        "Data": {
            "ReplicaCount": replica_count,
            "EnvironmentValue": env_value,
        },
    }
