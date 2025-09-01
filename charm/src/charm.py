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
        """Initialize the instance."""
        super().__init__(*args)
        self.redis = RedisRequires(self, relation_name="redis")
        self.framework.observe(self.on.redis_relation_changed, self._on_redis_relation_updated)
        # Initialize the stored state attributes
        self._stored.set_default(redis_connected=False)

    def _on_redis_relation_updated(self, event):
        """Handle Redis connection changes."""
        redis_url = self.redis.url
        if redis_url:
            if self._stored.redis_connected:
                logger.info("Redis reconnected. Restarting worker...")
                container = self.unit.get_container("flask-app")
                if container.can_connect():
                    container.restart("flask-scheduler")
            self.unit.status = ActiveStatus("Redis reconnected")
            self._stored.redis_connected = True
        else:
            self.unit.status = MaintenanceStatus("Redis connection lost")


if __name__ == "__main__":
    ops.main(LibraryCharmCharm)
