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
        self.framework.observe(self.on.worker_pebble_ready, self._on_worker_ready)

    def _on_flask_app_ready(self, event):
        """Handle Flask app readiness."""
        container = self.unit.get_container("flask-app")
        if container.can_connect():
            self._configure_flask_app(container)
            self.unit.status = ActiveStatus("Flask app is running")
            self._start_worker_if_ready()

    def _on_worker_ready(self, event):
        """Handle worker readiness."""
        container = self.unit.get_container("flask-scheduler")
        if container.can_connect():
            self._configure_worker(container)
            self._start_worker_if_ready()

    def _configure_flask_app(self, container):
        """Configure the Flask app service."""
        container.add_layer(
            "flask-app",
            {
                "services": {
                    "flask-app": {
                        "override": "replace",
                        "startup": "enabled",
                        "command": "python3 -m webapp.app",
                        "environment": {
                            "FLASK_ENV": "production",
                        },
                    }
                }
            },
            combine=True,
        )
        container.replan()

    def _configure_worker(self, container):
        """Configure the worker service."""
        container.add_layer(
            "flask-scheduler",
            {
                "services": {
                    "flask-scheduler": {
                        "override": "replace",
                        "startup": "disabled",  # Disabled until Flask app is running
                        "command": "python3 -m webapp.worker_cache",
                    }
                }
            },
            combine=True,
        )
        container.replan()

    def _start_worker_if_ready(self):
        """Start the worker only if the Flask app is running."""
        flask_container = self.unit.get_container("flask-app")
        worker_container = self.unit.get_container("flask-scheduler")

        if flask_container.can_connect() and worker_container.can_connect():
            flask_services = flask_container.get_plan().to_dict().get("services", {})
            if "flask-app" in flask_services and flask_services["flask-app"]["status"] == "active":
                worker_container.start("flask-scheduler")
                self.unit.status = ActiveStatus("Worker started")
            else:
                self.unit.status = MaintenanceStatus("Waiting for Flask app to start")
    
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
