import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if (
            "org" in self.scope
            and "external_user" in self.scope
            and "api_key" in self.scope
        ):
            org = self.scope["org"]
            external_user = self.scope["external_user"]
            await self.channel_layer.group_add(
                f"user_{external_user.id}", self.channel_name
            )
            await self.accept(self.scope["api_key"])
            logging.info(
                "Connection accepted on channel: %s for user: %s and org: %s",
                self.channel_name,
                external_user.id,
                org.id,
            )
        elif "error_code" in self.scope and "error_reason":
            await self.close(self.scope["error_code"], self.scope["error_reason"])
        else:
            await self.close()

    async def disconnect(self, close_code):
        org = self.scope["org"]
        external_user = self.scope["external_user"]
        await self.channel_layer.group_discard(
            f"user_{external_user.id}", self.channel_name
        )
        logging.debug(
            "Channel: %s with user: %s and org: %s disconnected with close code: %s",
            self.channel_name,
            external_user.id,
            org.id,
            close_code,
        )

    async def receive(self, text_data):
        org = self.scope["org"]
        external_user = self.scope["external_user"]
        logging.info(
            f"Channel: %s with user: %s and org: %s sent message: ",
            self.channel_name,
            external_user.id,
            org.id,
            text_data,
        )

    async def notification_created(self, event):
        org = self.scope["org"]
        external_user = self.scope["external_user"]
        json_data = json.dumps(event)
        await self.send(text_data=json_data)
        logging.info(
            "Web push notification sent for channel: %s with user: %s and org: %s with event: %s",
            self.channel_name,
            external_user.id,
            org.id,
            event,
        )
