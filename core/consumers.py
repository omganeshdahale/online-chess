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
        wq = WaitingQueue()
        wq.remove(self.user)
        self.abandon_if_ongoing()

    def receive(self, text_data):
        text_data_json = json.loads(text_data)

        if text_data_json["command"] == "move":
            self.move(text_data_json["san"])

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

        async_to_sync(self.channel_layer.group_add)(f"game_{g.pk}", self.channel_name)
        text_data = {
            "command": "start",
            "colour": g.get_colour(self.user),
            "opponent": g.get_opponent(self.user).username,
        }
        self.send(text_data=json.dumps(text_data))

    def abandon_if_ongoing(self):
        if not self.user.ongoing_game_exists():
            return

        g = self.user.get_ongoing_game()
        g.abandon()

        async_to_sync(self.channel_layer.group_discard)(
            f"game_{g.pk}", self.channel_name
        )
        async_to_sync(self.channel_layer.group_send)(
            f"game_{g.pk}",
            {"type": "abandoned", "game_pk": g.pk},
        )

    def abandoned(self, event):
        async_to_sync(self.channel_layer.group_discard)(
            f"game_{event['game_pk']}", self.channel_name
        )
        text_data = {"command": "abandoned"}
        self.send(text_data=json.dumps(text_data))
        self.close()

    def move(self, san):
        g = self.user.get_ongoing_game()
        if g.is_user_turn(self.user):
            if g.move(san):
                async_to_sync(self.channel_layer.group_send)(
                    f"game_{g.pk}",
                    {"type": "moved", "san": san, "colour": g.get_colour(self.user)},
                )

    def moved(self, event):
        g = self.user.get_ongoing_game()
        colour = g.get_colour(self.user)

        if colour != event["colour"]:
            text_data = {
                "command": "moved",
                "san": event["san"],
            }
            self.send(text_data=json.dumps(text_data))
