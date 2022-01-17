import chess
from django.conf import settings
from django.db import models


class Game(models.Model):
    ONGOING = "O"
    ABANDONED = "A"
    CHECKMATE = "C"
    DRAW = "D"

    STATUS_CHOICES = (
        (ONGOING, "ongoing"),
        (ABANDONED, "abandoned"),
        (CHECKMATE, "checkmate"),
        (DRAW, "draw"),
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
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="wins",
        on_delete=models.CASCADE,
        null=True,
    )
    created = models.DateTimeField(auto_now_add=True)

    def get_board(self):
        return chess.Board(self.fen)

    def is_player(self, user):
        return self.white == user or self.black == user

    def get_user_colour(self, user):
        return "white" if self.white == user else "black"

    def get_user_opponent(self, user):
        return self.black if self.white == user else self.white

    def move_if_legal(self, san):
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

    def get_turn_user(self):
        board = self.get_board()
        return self.white if board.turn else self.black

    def __str__(self):
        return f"#{self.pk}: {self.white} vs {self.black}"
