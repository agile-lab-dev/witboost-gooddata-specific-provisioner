from starlette.testclient import TestClient

from gooddata_sp.main import app

client = TestClient(app)

# TODO implement


def test_provisioning():
    pass
    #
    # provisioning_request = ProvisioningRequest(
    #     descriptorKind=DescriptorKind.COMPONENT_DESCRIPTOR, descriptor="descriptor"
    # )
    #
    # resp = client.post("/v1/provision", json=dict(provisioning_request))
    #
    # assert "Response not yet implemented" in resp.json().get("error")


def test_unprovisioning():
    pass
    #
    # provisioning_request = ProvisioningRequest(
    #     descriptorKind=DescriptorKind.COMPONENT_DESCRIPTOR, descriptor="descriptor"
    # )
    #
    # resp = client.post("/v1/unprovision", json=dict(provisioning_request))
    #
    # assert "Response not yet implemented" in resp.json().get("error")
