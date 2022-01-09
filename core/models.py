import chess
from django.conf import settings
from django.db import models


class Game(models.Model):
    white = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="games_as_white",
        on_delete=models.CASCADE,
    )
    black = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="games_as_black",
        on_delete=models.CASCADE,
    )
    fen = models.CharField(max_length=90)
    created = models.DateTimeField(auto_now_add=True)

    def get_board(self):
        return chess.Board(self.fen)

    def __str__(self):
        return f"#{self.pk}: {self.white} vs {self.black}"
