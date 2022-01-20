from datetime import timedelta
import chess
from django.conf import settings
from django.db import models
from django.utils import timezone


def validate_min_timer(value):
    if value < timedelta():
        raise ValidationError("Timer can't be negative.")


class Game(models.Model):
    ONGOING = "O"
    ABANDONED = "A"
    CHECKMATE = "C"
    TIMEOUT = "T"
    DRAW = "D"

    STATUS_CHOICES = (
        (ONGOING, "ongoing"),
        (ABANDONED, "abandoned"),
        (CHECKMATE, "checkmate"),
        (TIMEOUT, "timeout"),
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
    white_timer = models.DurationField(
        default=timedelta(),
        validators=[validate_min_timer],
    )
    black_timer = models.DurationField(
        default=timedelta(),
        validators=[validate_min_timer],
    )
    white_last_move_datetime = models.DateTimeField(null=True, blank=True)
    black_last_move_datetime = models.DateTimeField(null=True, blank=True)

    def get_board(self):
        return chess.Board(self.fen)

    def is_player(self, user):
        return self.white == user or self.black == user

    def get_user_colour(self, user):
        return "white" if self.white == user else "black"

    def get_user_opponent(self, user):
        return self.black if self.white == user else self.white

    def move_if_legal(self, san):
        """Play the move if legal and return True if successful, False otherwise."""
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

    def update_white_timer(self):
        now = timezone.now()
        self.white_last_move_datetime = now
        if self.black_last_move_datetime:
            diff = now - self.black_last_move_datetime
            self.white_timer += diff
        self.save()

    def update_black_timer(self):
        now = timezone.now()
        self.black_last_move_datetime = now
        diff = now - self.white_last_move_datetime
        self.black_timer += diff
        self.save()

    def is_white_timeup(self):
        if not self.get_board().turn:
            return False

        if not self.black_last_move_datetime:
            return False

        return timezone.now() >= self.get_white_deadline()

    def is_black_timeup(self):
        if self.get_board().turn:
            return False

        return timezone.now() >= self.get_black_deadline()

    def get_white_deadline(self):
        """Return datetime of when white runs out of time, assuming black has played."""
        return self.black_last_move_datetime + timedelta(minutes=10) - self.white_timer

    def get_black_deadline(self):
        """Return datetime of when black runs out of time, assuming white has played."""
        return self.white_last_move_datetime + timedelta(minutes=10) - self.black_timer

    def abandon(self, winner):
        self.status = self.ABANDONED
        self.winner = winner
        self.save()

    def checkmate(self, winner):
        self.status = self.CHECKMATE
        self.winner = winner
        self.save()

    def timeout(self, winner):
        self.status = self.TIMEOUT
        self.winner = winner
        self.save()

    def draw(self):
        self.status = self.DRAW
        self.save()

    def __str__(self):
        return f"#{self.pk}: {self.white} vs {self.black}"
