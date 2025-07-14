import redis

from app.core.config import settings

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True,
)


def get_redis() -> redis.Redis | None:
    try:
        redis_client.ping()
        return redis_client
    except redis.ConnectionError:
        return None
