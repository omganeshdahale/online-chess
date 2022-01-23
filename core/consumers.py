from datetime import timedelta
import json
import uuid
import chess
from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from django.utils import timezone, dateparse
from .waiting_queue import WaitingQueue


class GameConsumer(WebsocketConsumer):
    def connect(self):
        self.client_uuid = uuid.uuid4().hex
        self.in_waiting_queue = False
        self.game_uuid = ""

        async_to_sync(self.channel_layer.group_add)(
            f"client_{self.client_uuid}", self.channel_name
        )
        self.accept()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            f"client_{self.client_uuid}", self.channel_name
        )

        if self.in_waiting_queue:
            wq = WaitingQueue()
            wq.remove(self.client_uuid)

        elif self.game_uuid:
            async_to_sync(self.channel_layer.group_discard)(
                f"game_{self.game_uuid}", self.channel_name
            )
            async_to_sync(self.channel_layer.group_send)(
                f"game_{self.game_uuid}",
                {
                    "type": "inform_win",
                    "winner_colour": self.opponent_colour,
                    "by": "abandonment",
                },
            )

    def receive(self, text_data):
        text_data_json = json.loads(text_data)

        if text_data_json["command"] == "find_opponent":
            self.find_opponent_and_start()
        elif text_data_json["command"] == "move":
            self.move_if_legal(text_data_json["san"])
        elif text_data_json["command"] == "end_if_timeout":
            self.end_if_timeout()

    def find_opponent_and_start(self):
        if self.in_waiting_queue or self.game_uuid:
            return

        wq = WaitingQueue()
        opponent_uuid = wq.pop()
        if opponent_uuid:
            self.game_uuid = uuid.uuid4().hex
            self.client_colour = False
            self.opponent_uuid = opponent_uuid
            self.opponent_colour = True
            self.board = chess.Board()
            self.white_last_move_datetime = None
            self.black_last_move_datetime = None
            self.white_timer = timedelta()
            self.black_timer = timedelta()

            async_to_sync(self.channel_layer.group_add)(
                f"game_{self.game_uuid}", self.channel_name
            )
            async_to_sync(self.channel_layer.group_send)(
                f"client_{opponent_uuid}",
                {
                    "type": "start",
                    "game_uuid": self.game_uuid,
                    "client_uuid": self.client_uuid,
                },
            )
            self.inform_start()
        else:
            wq.push(self.client_uuid)
            self.in_waiting_queue = True

    def inform_start(self):
        text_data = {
            "command": "start",
            "client": self.client_uuid,
            "colour": self.bool_to_colour_str(self.client_colour),
            "opponent": self.opponent_uuid,
        }
        self.send(text_data=json.dumps(text_data))

    def start(self, event):
        self.in_waiting_queue = False
        self.game_uuid = event["game_uuid"]
        self.client_colour = True
        self.opponent_uuid = event["client_uuid"]
        self.opponent_colour = False
        self.board = chess.Board()
        self.white_last_move_datetime = None
        self.black_last_move_datetime = None
        self.white_timer = timedelta()
        self.black_timer = timedelta()

        async_to_sync(self.channel_layer.group_add)(
            f"game_{self.game_uuid}", self.channel_name
        )
        self.inform_start()

    def move_if_legal(self, san):
        if self.board.turn != self.client_colour:
            return

        try:
            move = self.board.parse_san(san)
        except ValueError:
            return

        if not move:  # null move
            return

        self.board.push(move)
        async_to_sync(self.channel_layer.group_send)(
            f"game_{self.game_uuid}",
            {
                "type": "moved",
                "san": san,
                "colour": self.client_colour,
                "time": timezone.now().isoformat(),
            },
        )

    def moved(self, event):
        if event["colour"]:
            self.update_white_timer(dateparse.parse_datetime(event["time"]))
            deadline = self.get_black_deadline().isoformat()
        else:
            self.update_black_timer(dateparse.parse_datetime(event["time"]))
            deadline = self.get_white_deadline().isoformat()

        text_data = {
            "command": "moved",
            "san": event["san"],
            "colour": self.bool_to_colour_str(event["colour"]),
            "deadline": deadline,
        }
        self.send(text_data=json.dumps(text_data))

        if event["colour"] == self.client_colour:
            self.end_if_gameover()
        else:
            self.board.push_san(event["san"])

    def end_if_gameover(self):
        if self.board.is_checkmate():
            async_to_sync(self.channel_layer.group_send)(
                f"game_{self.game_uuid}",
                {
                    "type": "inform_win",
                    "winner_colour": self.client_colour,
                    "by": "checkmate",
                },
            )
        elif (
            self.board.is_stalemate()
            or self.board.is_insufficient_material()
            or self.board.is_fifty_moves()
            or self.board.is_repetition()
        ):
            async_to_sync(self.channel_layer.group_send)(
                f"game_{self.game_uuid}",
                {
                    "type": "inform_draw",
                },
            )

    def inform_win(self, event):
        self.game_uuid = ""
        self.black_last_move_datetime = None
        text_data = {
            "command": "win",
            "winner_colour": self.bool_to_colour_str(event["winner_colour"]),
            "by": event["by"],
        }
        self.send(text_data=json.dumps(text_data))

    def inform_draw(self, event):
        self.game_uuid = ""
        self.black_last_move_datetime = None
        self.send(text_data=json.dumps({"command": "draw"}))

    def end_if_timeout(self):
        if self.is_white_timeup():
            async_to_sync(self.channel_layer.group_send)(
                f"game_{self.game_uuid}",
                {
                    "type": "inform_win",
                    "winner_colour": False,
                    "by": "timeout",
                },
            )

        elif self.is_black_timeup():
            async_to_sync(self.channel_layer.group_send)(
                f"game_{self.game_uuid}",
                {
                    "type": "inform_win",
                    "winner_colour": True,
                    "by": "timeout",
                },
            )

    def bool_to_colour_str(self, b):
        return "white" if b else "black"

    def update_white_timer(self, time):
        self.white_last_move_datetime = time
        if self.black_last_move_datetime:
            diff = time - self.black_last_move_datetime
            self.white_timer += diff

    def update_black_timer(self, time):
        self.black_last_move_datetime = time
        diff = time - self.white_last_move_datetime
        self.black_timer += diff

    def get_white_deadline(self):
        """Return datetime of when white runs out of time, assuming black has played."""
        return self.black_last_move_datetime + timedelta(minutes=10) - self.white_timer

    def get_black_deadline(self):
        """Return datetime of when black runs out of time, assuming white has played."""
        return self.white_last_move_datetime + timedelta(minutes=10) - self.black_timer

    def is_white_timeup(self):
        if not self.board.turn:
            return False

        if not self.black_last_move_datetime:
            return False

        return timezone.now() >= self.get_white_deadline()

    def is_black_timeup(self):
        if self.board.turn:
            return False

        return timezone.now() >= self.get_black_deadline()
