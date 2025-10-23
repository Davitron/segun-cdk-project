# AWS CDK EKS Platform Infrastructure

A multi-environment AWS CDK project that deploys a complete EKS (Kubernetes) platform with networking, cluster, and ingress controller components.

## Architecture Overview

![Architecture Diagram](./arch.png)

This project builds a complete Kubernetes platform on AWS using three main components that work together: first we create the network foundation with VPC and subnets, then we add the EKS cluster on top of that network, and finally we deploy the Nginx ingress controller to handle incoming traffic. The ingress controller includes a custom Lambda function that automatically adjusts the number of replicas based on the environment. One replica for development and two for staging/production. Each environment (development/staging/production) gets its own isolated setup with different configurations.

#### Why this approach?
Breaking the infrastructure into separate, dependent stacks makes deployments more reliable and easier to manage. You can deploy just the network changes without touching the cluster, or update the ingress controller independently.

## Stack Dependencies

1. **NetworkStack** → Creates VPC infrastructure (no dependencies)
2. **ClusterStack** → Creates EKS cluster (depends on NetworkStack VPC)
3. **NginxIngressStack** → Deploys ingress controller (depends on ClusterStack)

## Environment Configuration

The project supports multiple environments configured in `cdk.json` context:

```json
{
  "context": {
    "service_name": "your-service-name",
    "dev": {
      "env": "development",
      "account_id": "123456789012",
      "region": "us-east-1",
      "vpc_cidr": "172.16.0.0/16"
    },
    "stg": {
      "env": "staging", 
      "account_id": "123456789012",
      "region": "us-east-1",
      "vpc_cidr": "10.0.0.0/16"
    },
    "prod": {
      "env": "production",
      "account_id": "987654321098",
      "region": "us-east-1", 
      "vpc_cidr": "10.0.50.0/16"
    }
  }
}
```

**Configuration Parameters:**
- `service_name`: Base name for all resources
- `env`: Environment name for tagging and identification
- `account_id`: AWS account ID for deployment
- `region`: AWS region for resource deployment
- `vpc_cidr`: CIDR block for VPC (must not overlap between environments)

## Prerequisites

- **Python 3.13+**
- **Node.js 18+** (for AWS CDK CLI)
- **AWS CLI** configured with appropriate credentials
- **kubectl** (for cluster access)

## Setup and Installation

### 1. Clone and Navigate
```bash
git clone <repository-url>
cd segun-cdk-project
```

### 2. Install AWS CDK CLI
```bash
npm install -g aws-cdk
```

### 3. Create Python Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 4. Install Dependencies
```bash
# Install runtime dependencies
pip install -r requirements.txt

# Install development dependencies (for testing/linting)
pip install -r requirements-dev.txt
```

### 5. Configure AWS Credentials
```bash
aws configure
# OR export AWS_PROFILE=your-profile-name
```

### 6. Update Context Configuration
Edit `cdk.json` to configure your environment settings:
```bash
# Open cdk.json and update the context section with your values
# Replace placeholders in the "context" section:
# - service_name: Your project name
# - account_id: Your AWS account ID(s)  
# - region: Your preferred AWS region
# - vpc_cidr: CIDR blocks for each environment
```

### 7. Bootstrap CDK (First Time Only)
```bash
cdk bootstrap --context environment=<env> # where env is (dev|stg|prod)
```

## Deployment

### Deploy to Development Environment
```bash
# Synthesize and review changes
cdk synth --context environment=dev

# Deploy all stacks
cdk deploy --all --context environment=dev

# Deploy all stacks without approval prompts (for automation)
cdk deploy --all --context environment=dev --require-approval=never

# Deploy specific stack
cdk deploy NetworkStack --context environment=dev
```

### Deploy to Staging/Production
```bash
# Staging
cdk deploy --all --context environment=stg

# Staging (no approval prompts)
cdk deploy --all --context environment=stg --require-approval=never

# Production
cdk deploy --all --context environment=prod

# Production (no approval prompts)
cdk deploy --all --context environment=prod --require-approval=never
```

### Configure kubectl Access
After cluster deployment, configure kubectl:
```bash
aws eks update-kubeconfig --name <service_name> --region <region>

# Example for dev environment:
# aws eks update-kubeconfig --name your-service-name --region us-east-1
```

## Testing

### Run All Tests
```bash
pytest
```

### Run Specific Test Files
```bash
# Network stack tests
pytest tests/unit/test_network_stack.py

# Cluster stack tests  
pytest tests/unit/test_cluster_stack.py

# Platform stack tests
pytest tests/unit/test_platform_stack.py

# Lambda handler tests
pytest tests/unit/test_lambda_handler.py
```

### Run Tests with Coverage
```bash
pytest --cov=stacks --cov=assets --cov-report=html
```

### Test Categories

- **Unit Tests**: Validate CDK stack synthesis and resource properties
- **CIDR Validation**: Test VPC CIDR format validation
- **Tagging Tests**: Verify Kubernetes subnet tagging for ELB discovery
- **Lambda Tests**: Test custom resource logic with mocked AWS services

## Linting and Code Quality

### Run Pylint
```bash
# Lint all Python files
pylint stacks/ assets/ tests/ app.py

# Lint specific module
pylint stacks/network/network_stack.py

# Generate pylint report
pylint stacks/ assets/ tests/ app.py --output-format=html > pylint-report.html
```

### Pylint Configuration
Pylint settings are configured in `.pylintrc`:
- Disabled checks: `redefined-outer-name` (common in test fixtures)
- Line length: 150 characters
- Ignores: `.venv`, `__pycache__`, `.git`, `.pytest_cache`, `cdk.out`


### Code Style Guidelines
- **Docstrings**: All modules, classes, and functions must have docstrings
- **Type Hints**: Use type annotations for function parameters and returns
- **Imports**: Group imports (standard library, third-party, local)
- **Line Length**: Maximum 100 characters

## Project Structure

```
segun-cdk-project/
├── app.py                          # CDK application entry point
├── cdk.json                        # CDK configuration and context
├── requirements.txt                # Runtime dependencies
├── requirements-dev.txt            # Development dependencies
├── pytest.ini                     # Pytest configuration
├── .pylintrc                      # Pylint configuration
├── stacks/                        # CDK stack definitions
│   ├── network/
│   │   └── network_stack.py       # VPC and networking resources
│   ├── cluster/
│   │   └── cluster_stacks.py      # EKS cluster and node groups
│   └── platform/
│       └── nginx_ingress_stack.py # Nginx ingress controller
├── assets/
│   └── _lambda/
│       └── handler.py             # Custom resource Lambda function
└── tests/
    └── unit/
        ├── test_network_stack.py   # Network stack tests
        ├── test_cluster_stack.py   # Cluster stack tests
        ├── test_platform_stack.py  # Platform stack tests
        └── test_lambda_handler.py  # Lambda handler tests
```

## Key Features

### NetworkStack
- **Multi-AZ VPC** with configurable CIDR blocks
- **Public subnets** (3 AZs) tagged for external load balancers
- **Private subnets** (3 AZs) tagged for internal load balancers
- **Kubernetes cluster discovery tags** for EKS integration
- **Single NAT Gateway**
- **Single Internet Gateway**

### ClusterStack
- **EKS v1.33** with API and ConfigMap authentication
- **Bottlerocket managed node groups** for security and performance
- **IAM access entries** for user permissions
- **SSM parameter** for environment configuration

### NginxIngressStack
- **Helm chart deployment** for Nginx ingress controller
- **Custom resource** for dynamic replica count (dev:1, stg/prod:2)
- **IAM roles** with least privilege principles

## Environment-Specific Deployment Commands

```bash
# Development
cdk deploy --all --context environment=dev

# Development (no approval prompts)
cdk deploy --all --context environment=dev --require-approval=never

# Staging  
cdk deploy --all --context environment=stg

# Staging (no approval prompts)
cdk deploy --all --context environment=stg --require-approval=never

# Production
cdk deploy --all --context environment=prod

# Production (no approval prompts)
cdk deploy --all --context environment=prod --require-approval=never
```

## Cleanup

### Destroy All Stacks
```bash
# Destroy in reverse dependency order
cdk destroy NginxIngressStack --context environment=dev
cdk destroy ClusterStack --context environment=dev
cdk destroy NetworkStack --context environment=dev

# Or destroy all at once (CDK handles order)
cdk destroy --all --context environment=dev
```