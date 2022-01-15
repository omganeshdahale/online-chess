import chess
from django.conf import settings
from django.db import models


class Game(models.Model):
    ONGOING = "O"
    ABANDONED = "A"
    COMPLETED = "C"

    STATUS_CHOICES = (
        (ONGOING, "ongoing"),
        (ABANDONED, "abandoned"),
        (COMPLETED, "completed"),
    )

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
    fen = models.CharField(
        max_length=90,
        default="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    )
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=ONGOING)
    created = models.DateTimeField(auto_now_add=True)

    def get_board(self):
        return chess.Board(self.fen)

    def is_player(self, user):
        return self.white == user or self.black == user

    def get_colour(self, user):
        return "white" if self.white == user else "black"

    def abandon(self):
        self.status = self.ABANDONED
        self.save()

    def get_opponent(self, user):
        return self.black if self.white == user else self.white

    def is_user_turn(self, user):
        board = self.get_board()
        colour = self.get_colour(user)

        return board.turn and colour == "white" or not board.turn and colour == "black"

    def move(self, san):
        board = self.get_board()
        try:
            m = board.parse_san(san)
        except ValueError:
            return False

        if not m:
            return False

        board.push(m)
        self.fen = board.fen()
        self.save()
        return True

    def __str__(self):
        return f"#{self.pk}: {self.white} vs {self.black}"
