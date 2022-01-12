from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Sum
from core.models import Game


class User(AbstractUser):
    pass

    def ongoing_game_exists(self):
        return Game.objects.filter(
            models.Q(white=self) | models.Q(black=self), status=Game.ONGOING
        ).exists()

    def get_ongoing_game(self):
        return Game.objects.get(
            models.Q(white=self) | models.Q(black=self), status=Game.ONGOING
        )
