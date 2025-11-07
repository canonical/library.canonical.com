import os
from flask_caching import Cache
try:
    from webapp.db import db 
except Exception: 
    db = None  


cache = Cache()


def init_cache(app) -> None:
    """Initialize the Flask-Caching extension using env configuration.

    - If REDIS_DB_CONNECT_STRING is set, use RedisCache with that URL.
    - Otherwise, fall back to SimpleCache.
    """
    if os.getenv("REDIS_DB_CONNECT_STRING"):
        app.config.setdefault("CACHE_TYPE", "RedisCache")
        app.config.setdefault(
            "CACHE_REDIS_URL",
            os.getenv("REDIS_DB_CONNECT_STRING", "redis://localhost:6379"),
        )
        print("\n\nUsing Redis cache\n\n", flush=True)
    else:
        app.config.setdefault("CACHE_TYPE", "simple")

    cache.init_app(app)
