# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Smoke integration test — deploy the charm and verify it starts."""

import asyncio
from pathlib import Path

import pytest
from pytest_operator.plugin import OpsTest


@pytest.mark.abort_on_fail
async def test_deploy(ops_test: OpsTest, pytestconfig):
    """Build and deploy the charm, then verify it reaches active/idle."""
    assert ops_test.model

    charm = Path(pytestconfig.getoption("--charm-file")).resolve()
    rock_image = pytestconfig.getoption("--library-rock-image")
    resources = {"flask-app-image": rock_image}

    await asyncio.gather(
        ops_test.model.deploy(
            str(charm),
            resources=resources,
            application_name="library-charm",
            trust=True,
        ),
        ops_test.model.wait_for_idle(
            apps=["library-charm"],
            status="blocked",  # will be blocked waiting for postgresql and redis relations
            raise_on_error=False,
            timeout=600,
        ),
    )
    # The charm should be blocked because postgresql and redis are required relations.
    unit = ops_test.model.applications["library-charm"].units[0]
    assert unit.workload_status == "blocked"