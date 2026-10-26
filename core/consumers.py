# core/consumers.py
import json
from channels.generic.websocket import WebsocketConsumer

class SurveillanceConsumer(WebsocketConsumer):
    def connect(self):
        self.room_group_name = "secure_vision_dashboard"
        self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        self.accept()

    def disconnect(self, close_code):
        self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    def receive(self, text_data):
        pass

    def send_alert(self, event):
        message = event['message']
        self.send(text_data=json.dumps(message))