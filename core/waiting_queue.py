import redis
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()

# connect to redis
r = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True,
)


class WaitingQueue:
    KEY = "waiting-queue"

    def push(self, user):
        r.rpush(self.KEY, str(user.pk))

    def pop(self):
        pk = r.lpop(self.KEY)
        if pk:
            return User.objects.get(pk=int(pk))

    def search(self, user):
        return str(user.pk) in r.lrange(self.KEY, 0, -1)

    def remove(self, user):
        r.lrem(self.KEY, 0, str(user.pk))
