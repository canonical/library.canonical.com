# Copyright 2025 Ubuntu
# See LICENSE file for licensing details.

"""Configuration for the integration tests."""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--charm-file",
        action="store",
        help="Path to the built charm file.",
    )


@pytest.fixture(scope="module")
def charm_file(request):
    """Return the path to the charm file passed via --charm-file."""
    return request.config.getoption("--charm-file")
