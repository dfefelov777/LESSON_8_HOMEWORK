import redis
import time
import os
from typing import Optional


class RedisStore:
    def __init__(self, host=None, port=None, db=0, retries=3, retry_timeout=0.5):
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT", "6379"))
        self.db = db
        self.retries = retries
        self.retry_timeout = retry_timeout
        self._connect()

    def _connect(self):
        self.client = redis.Redis(
            host=self.host, port=self.port, db=self.db, socket_timeout=1
        )

    def _retry(func):
        def wrapper(self, *args, **kwargs):
            last_exception = None
            for _ in range(self.retries):
                try:
                    return func(self, *args, **kwargs)
                except (redis.ConnectionError, redis.TimeoutError) as e:
                    last_exception = e
                    self._connect()
                    time.sleep(self.retry_timeout)
            raise last_exception

        return wrapper

    @_retry
    def get(self, key: str) -> Optional[str]:
        value = self.client.get(key)
        if value is not None:
            return value.decode("utf-8")
        return None

    @_retry
    def cache_get(self, key: str) -> Optional[str]:
        value = self.client.get(key)
        if value is not None:
            return value.decode("utf-8")
        return None

    @_retry
    def cache_set(self, key: str, value, expires: int):
        self.client.setex(key, expires, value)
