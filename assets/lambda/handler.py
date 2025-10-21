import boto3, os, json, traceback
from botocore.exceptions import ClientError, BotoCoreError

ssm = boto3.client("ssm")

def _replicas_from_env(env_value: str) -> int:
    env_value = (env_value or "").strip().lower()
    if env_value == "development":
        return 1
    if env_value == "staging" or env_value == "production":
        return 2
    return 1  # default fallback

def _get_env_value(param_name: str) -> str:
    try:
        response = ssm.get_parameter(Name=param_name)
        return response["Parameter"]["Value"]
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "ParameterNotFound":
            print(f"Parameter {param_name} not found; falling back to development")
            return "development"
        # Other client errors: log and fallback
        print(f"ClientError retrieving {param_name}: {error_code}. Fallback to development")
        return "development"
    except BotoCoreError as e:
        print(f"BotoCoreError retrieving {param_name}: {e}. Fallback to development")
        return "development"
    except Exception:
        print("Unexpected exception retrieving", param_name, traceback.format_exc())
        return "development"

def on_event(event, context):
    request_type = event.get("RequestType", "Create")
    param_name = os.environ.get("ENVIRONMENT")

    if not param_name:
        raise RuntimeError("ENVIRONMENT environment variable is required")

    # For Delete, return a stable physical id and a safe default
    if request_type == "Delete":
        return {
            "PhysicalResourceId": param_name,
            "Data": {"ReplicaCount": 1},
        }

    # For Create/Update fetch environment and map to replica count
    env_value = _get_env_value(param_name)
    replica_count = _replicas_from_env(env_value)

    # Return numeric value (CloudFormation will treat it as a primitive via get_att)
    return {
        "PhysicalResourceId": param_name,
        "Data": {
            "ReplicaCount": replica_count,
            "EnvironmentValue": env_value,
        },
    }

