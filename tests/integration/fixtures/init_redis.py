import redis
import os


def init_redis():
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))

    client = redis.Redis(host=host, port=port, db=0)

    # Установим пример данных
    client.set("i:1", '["books", "music"]')
    client.set("i:2", '["travel", "sports"]')
    client.set("i:3", '["movies", "tech"]')


if __name__ == "__main__":
    init_redis()
