import json
import chess
from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from .models import Game
from .waiting_queue import WaitingQueue


class GameConsumer(WebsocketConsumer):
    def connect(self):
        if self.scope["user"].is_anonymous:
            return self.close()
        self.user = self.scope["user"]

        if not self.allow_connect():
            return self.close()

        async_to_sync(self.channel_layer.group_add)("global", self.channel_name)
        self.accept()

        self.find_opponent_and_start()

    def disconnect(self, close_code):
        if close_code == 1006:
            return

        async_to_sync(self.channel_layer.group_discard)("global", self.channel_name)
        if hasattr(self, "game_pk"):
            async_to_sync(self.channel_layer.group_discard)(
                f"game_{self.game_pk}", self.channel_name
            )

        wq = WaitingQueue()
        wq.remove(self.user)
        self.abandon_if_ongoing()

    def receive(self, text_data):
        text_data_json = json.loads(text_data)

        if text_data_json["command"] == "move":
            self.move_if_legal(text_data_json["san"])
            self.end_if_gameover()
        elif text_data_json["command"] == "end_if_timeout":
            self.end_if_timeout()

    def allow_connect(self):
        if self.user.ongoing_game_exists():
            return False

        wq = WaitingQueue()
        return not wq.search(self.user)

    def find_opponent_and_start(self):
        wq = WaitingQueue()
        opponent = wq.pop()
        if opponent:
            g = Game.objects.create(white=opponent, black=self.user)
            async_to_sync(self.channel_layer.group_send)(
                "global",
                {
                    "type": "start",
                    "game_pk": g.pk,
                },
            )
        else:
            wq.push(self.user)

    def start(self, event):
        g = Game.objects.get(pk=event["game_pk"])
        if not g.is_player(self.user):
            return

        self.game_pk = g.pk
        self.colour = g.get_user_colour(self.user)
        self.opponent = g.get_user_opponent(self.user)
        self.opponent_colour = g.get_user_colour(self.opponent)

        async_to_sync(self.channel_layer.group_add)(f"game_{g.pk}", self.channel_name)
        text_data = {
            "command": "start",
            "colour": self.colour,
            "opponent": self.opponent.username,
        }
        self.send(text_data=json.dumps(text_data))

    def abandon_if_ongoing(self):
        if not hasattr(self, "game_pk"):  # game not even started yet
            return

        g = Game.objects.get(pk=self.game_pk)
        if g.status != g.ONGOING:  # game ended
            return

        g.abandon(self.opponent)

        async_to_sync(self.channel_layer.group_send)(
            f"game_{self.game_pk}",
            {
                "type": "end_by_win",
                "winner_col": self.opponent_colour,
                "by": "abandonment",
            },
        )

    def move_if_legal(self, san):
        g = Game.objects.get(pk=self.game_pk)
        if g.get_turn_user() != self.user:
            return

        if not g.move_if_legal(san):
            return

        if self.colour == "white":
            g.update_white_timer()
        else:
            g.update_black_timer()

        async_to_sync(self.channel_layer.group_send)(
            f"game_{self.game_pk}",
            {"type": "moved", "san": san, "colour": self.colour},
        )

    def moved(self, event):
        g = Game.objects.get(pk=self.game_pk)
        if event["colour"] == "white":
            deadline = g.get_black_deadline().isoformat()
        else:
            deadline = g.get_white_deadline().isoformat()

        text_data = {
            "command": "moved",
            "san": event["san"],
            "colour": event["colour"],
            "deadline": deadline,
        }
        self.send(text_data=json.dumps(text_data))

    def end_if_gameover(self):
        g = Game.objects.get(pk=self.game_pk)
        board = g.get_board()

        if board.is_checkmate():
            g.checkmate(self.user)
            async_to_sync(self.channel_layer.group_send)(
                f"game_{self.game_pk}",
                {
                    "type": "end_by_win",
                    "winner_col": self.colour,
                    "by": "checkmate",
                },
            )
        elif (
            board.is_stalemate()
            or board.is_insufficient_material()
            or board.is_fifty_moves()
            or board.is_repetition()
        ):
            g.draw()
            async_to_sync(self.channel_layer.group_send)(
                f"game_{self.game_pk}",
                {
                    "type": "end_by_draw",
                },
            )

    def end_by_win(self, event):
        text_data = {
            "command": "win",
            "winner_col": event["winner_col"],
            "by": event["by"],
        }
        self.send(text_data=json.dumps(text_data))
        self.close()

    def end_by_draw(self, event):
        text_data = {"command": "draw"}
        self.send(text_data=json.dumps(text_data))
        self.close()

    def end_if_timeout(self):
        g = Game.objects.get(pk=self.game_pk)
        if g.is_white_timeup():
            g.timeout(g.black)
            async_to_sync(self.channel_layer.group_send)(
                f"game_{self.game_pk}",
                {
                    "type": "end_by_win",
                    "winner_col": "black",
                    "by": "timeout",
                },
            )

        elif g.is_black_timeup():
            g.timeout(g.white)
            async_to_sync(self.channel_layer.group_send)(
                f"game_{self.game_pk}",
                {
                    "type": "end_by_win",
                    "winner_col": "white",
                    "by": "timeout",
                },
            )
