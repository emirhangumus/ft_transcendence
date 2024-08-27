from channels.generic.websocket import AsyncWebsocketConsumer
import json


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = "dashboard"
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.accept()

    async def receive(self, text_data):
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "data_pusher",
                "text": text_data,
            },
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def data_pusher(self, event):
        await self.send(text_data=event["text"])