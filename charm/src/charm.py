#!/usr/bin/env python3
# Copyright 2025 Ubuntu
# See LICENSE file for licensing details.

"""Flask Charm entrypoint."""

import logging
import typing
import ops
import paas_charm.flask

from ops.framework import StoredState
from charms.redis_k8s.v0.redis import RedisRequires
from ops.model import ActiveStatus, MaintenanceStatus

logger = logging.getLogger(__name__)


class LibraryCharmCharm(paas_charm.flask.Charm):
    """Flask Charm service."""
    _stored = StoredState()

    def __init__(self, *args: typing.Any) -> None:
        """Initialize the instance.
        Args:args: passthrough to CharmBase.
        """
        super().__init__(*args)
        self.redis = RedisRequires(self, relation_name="redis")
        self.framework.observe(self.on.redis_relation_changed, self._on_redis_relation_updated)
        self.framework.observe(self.on.flask_app_pebble_ready, self._on_flask_app_ready)

    def _on_flask_app_ready(self, event):
        """Handle Flask app readiness."""
        container = self.unit.get_container("flask-app")
        if container.can_connect():
            self._configure_flask_app_and_worker(container)
            self.unit.status = ActiveStatus("Flask app and worker are running")

    def _configure_flask_app_and_worker(self, container):
        """Configure the Flask app and worker services in the same container."""
        container.add_layer(
            "flask-app-and-worker",
            {
                "services": {
                    "flask-app": {
                        "override": "replace",
                        "startup": "enabled",
                        "command": "python3 -m webapp.app",
                        "environment": {
                            "FLASK_ENV": "production",
                        },
                    },
                    "flask-scheduler": {
                        "override": "replace",
                        "startup": "enabled",  # Start the worker alongside the Flask app
                        "command": "python3 -m webapp.worker_cache",
                    },
                }
            },
            combine=True,
        )
        container.replan()
    
    def _on_redis_relation_updated(self, event):
        """Handle Redis connection changes."""
        redis_url = self.redis.url
        if redis_url:
            if self._stored.redis_connected:
                print("Redis reconnected. Restarting worker...", flush=True)
                container = self.unit.get_container("flask-scheduler")
                if container.can_connect():
                    container.restart("flask-scheduler")
            self.unit.status = ActiveStatus("Redis reconnected")
            self._stored.redis_connected = True
        else:
            self.unit.status = MaintenanceStatus("Redis connection lost")

if __name__ == "__main__":
    ops.main(LibraryCharmCharm)
