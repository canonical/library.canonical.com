# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration test fixtures."""


def pytest_addoption(parser):
    """Parse additional pytest options.

    Args:
        parser: Pytest parser.
    """
    parser.addoption("--charm-file", action="store")
    parser.addoption("--library-rock-image", action="store")