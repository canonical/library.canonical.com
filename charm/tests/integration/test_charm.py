# Copyright 2025 Ubuntu
# See LICENSE file for licensing details.

"""Integration tests for the library-canonical charm."""

import pytest


@pytest.mark.asyncio
async def test_deploy(ops_test, charm_file):
    """Test that the charm deploys and reaches a known workload status."""
    app = await ops_test.model.deploy(
        charm_file,
        application_name="library-charm",
        num_units=1,
    )
    await ops_test.model.wait_for_idle(
        apps=["library-charm"],
        timeout=300,
        raise_on_blocked=False,
        raise_on_error=False,
    )
    unit = ops_test.model.applications["library-charm"].units[0]
    assert unit.workload_status in ("active", "blocked"), (
        f"Unexpected workload status: {unit.workload_status} — {unit.workload_status_message}"
    )
