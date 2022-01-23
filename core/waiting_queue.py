import redis
from django.conf import settings

# connect to redis
r = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True,
)


class WaitingQueue:
    KEY = "waiting-queue"

    def push(self, val):
        r.rpush(self.KEY, val)

    def pop(self):
        return r.lpop(self.KEY)

    def search(self, val):
        return str(val) in r.lrange(self.KEY, 0, -1)

    def remove(self, val):
        r.lrem(self.KEY, 0, val)
