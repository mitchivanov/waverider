from channels.generic.websocket import AsyncWebsocketConsumer
import json

class BotConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add('bot_updates', self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard('bot_updates', self.channel_name)

    # Receive message from WebSocket
    async def receive(self, text_data):
        pass  # Not handling any incoming messages from the frontend

    # Receive message from bot and send to WebSocket
    async def bot_update(self, event):
        await self.send(text_data=json.dumps(event['message']))

