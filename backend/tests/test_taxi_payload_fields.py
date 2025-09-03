import pytest
import sys
import os

# Ensure backend package is on path when running from repo root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.taxi_models import VMRequest, AppEnvironment, OS, UseType, LineOfBusiness
from mcp_server.server import MCPServer


def make_minimal_vmrequest():
    return VMRequest(
        appEnvironment=AppEnvironment.NONPROD,
        lineOfBusiness=LineOfBusiness.RETAIL,
        costCenter="12453",
        project="dwayne-dwayne",
        zone="us-central1-b",
        os=OS.LINUX_RHEL9,
        useType=UseType.APP,
        machineType="n4-standard-4",
        id="dwayne@lazelabs.com",
    )


def test_vmrequest_to_taxi_payload_shape():
    vmr = make_minimal_vmrequest()
    payload = vmr.to_taxi_payload()

    # Top-level fields
    assert payload["project"] == "dwayne-dwayne"
    assert payload["zone"] == "us-central1-b"
    assert payload["os"] == "LINUX_RHEL9"
    assert payload["useType"] == "app"
    assert payload["machineType"] == "n4-standard-4"

    # resourceMetadata additions
    rm = payload.get("resourceMetadata", {})
    assert rm.get("cloud") == "GCP"
    assert rm.get("resourceType") == "compute"
    assert rm.get("appEnvironment") == "NONPROD"
    assert rm.get("lineOfBusiness") == "RETAIL"
    assert rm.get("costCenter") == "12453"

    # options additions
    opts = payload.get("options", {})
    assert opts.get("action") == "create"
    assert opts.get("requestSource") == "ISTS"
    assert opts.get("requestor", {}).get("id") == "dwayne@lazelabs.com"


def test_mcp_server_build_taxi_payload_shape():
    server = MCPServer()
    vm = {
        "appEnvironment": "NONPROD",
        "appEnvironmentSubtype": "dev",
        "lineOfBusiness": "RETAIL",
        "costCenter": "12453",
        "project": "dwayne-dwayne",
        "zone": "us-central1-b",
        "os": "LINUX_RHEL9",
        "useType": "app",
        "machineType": "n4-standard-4",
        "id": "dwayne@lazelabs.com",
    }
    payload = server._build_taxi_payload(vm)
    rm = payload.get("resourceMetadata", {})
    assert rm.get("cloud") == "GCP"
    assert rm.get("resourceType") == "compute"
    opts = payload.get("options", {})
    assert opts.get("action") == "create"
