import json

from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if (
            "org" in self.scope
            and "external_user" in self.scope
            and "api_key" in self.scope
        ):
            external_user = self.scope["external_user"]
            await self.channel_layer.group_add(
                f"user_{external_user.id}", self.channel_name
            )
            await self.accept(self.scope["api_key"])
        elif "api_key" in self.scope:
            await self.close(self.scope["api_key"])
        else:
            await self.close()

    async def disconnect(self, close_code):
        print("channel disconnected!")

    async def receive(self, text_data):
        print("message received!")

    async def notification_created(self, event):
        await self.send(text_data=json.dumps(event))
