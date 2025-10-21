import boto3
import pytest
from moto import mock_aws
from botocore.stub import Stubber
from botocore.exceptions import EndpointConnectionError

from assets._lambda import handler as lf


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "/platform/account/env")


@pytest.fixture
def ssm_client_moto():
    with mock_aws():
        yield boto3.client("ssm")


def _invoke(event=None):
    event = event or {"RequestType": "Create"}
    return lf.on_event(event, None)


def test_create_staging_returns_2(ssm_client_moto, monkeypatch):
    # Point the module-level SSM client to a moto-backed client
    monkeypatch.setattr(lf, "ssm", ssm_client_moto)
    ssm_client_moto.put_parameter(Name="/platform/account/env", Value="staging", Type="String")

    result = _invoke()
    assert result["Data"]["ReplicaCount"] == 2
    assert result["Data"]["EnvironmentValue"] == "staging"


def test_create_development_returns_1(ssm_client_moto, monkeypatch):
    monkeypatch.setattr(lf, "ssm", ssm_client_moto)
    ssm_client_moto.put_parameter(Name="/platform/account/env", Value="development", Type="String")

    result = _invoke()
    assert result["Data"]["ReplicaCount"] == 1
    assert result["Data"]["EnvironmentValue"] == "development"


def test_create_production_returns_2(ssm_client_moto, monkeypatch):
    monkeypatch.setattr(lf, "ssm", ssm_client_moto)
    ssm_client_moto.put_parameter(Name="/platform/account/env", Value="production", Type="String")

    result = _invoke()
    assert result["Data"]["ReplicaCount"] == 2
    assert result["Data"]["EnvironmentValue"] == "production"


def test_missing_parameter_falls_back_to_development(ssm_client_moto, monkeypatch):
    monkeypatch.setattr(lf, "ssm", ssm_client_moto)
    result = _invoke()
    assert result["Data"]["ReplicaCount"] == 1
    assert result["Data"]["EnvironmentValue"] == "development"


def test_delete_returns_safe_default(monkeypatch):
    # No SSM access should be needed on Delete
    monkeypatch.setenv("ENVIRONMENT", "/another/env")

    result = _invoke({"RequestType": "Delete"})
    assert result["Data"]["ReplicaCount"] == 1
    assert "EnvironmentValue" not in result["Data"]


def test_missing_env_var_raises(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    with pytest.raises(RuntimeError) as ei:
        _invoke()
    assert "ENVIRONMENT environment variable is required" in str(ei.value)


def test_other_client_error_falls_back_to_development(ssm_client_moto, monkeypatch):
    # Use a Stubber to force a non-ParameterNotFound client error
    monkeypatch.setattr(lf, "ssm", ssm_client_moto)
    stubber = Stubber(ssm_client_moto)
    stubber.add_client_error("get_parameter", service_error_code="AccessDeniedException")
    stubber.activate()

    try:
        result = _invoke()
        assert result["Data"]["ReplicaCount"] == 1
        assert result["Data"]["EnvironmentValue"] == "development"
    finally:
        stubber.deactivate()

