from channels.generic.websocket import AsyncWebsocketConsumer
import json

# The `ChatConsumer` class is an asynchronous WebSocket consumer that handles connecting,
# disconnecting, receiving messages, and broadcasting messages to a chat channel.
class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """
        The `connect` function adds the current channel to a group and accepts the connection.
        """
        self.channel_name = self.scope["url_route"]["kwargs"]["channel"]

        await self.channel_layer.group_add(self.channel_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        """
        The `disconnect` function removes the current channel from the group.
        
        :param close_code: The close_code parameter is an integer that represents the reason for the
        disconnection. It is typically used to indicate the reason for closing a WebSocket connection
        """
        await self.channel_layer.group_discard(self.channel_name, self.channel_name)

    async def receive(self, text_data):
        """
        The `receive` function receives a message, extracts the message content, and broadcasts it to
        the chat channel.
        
        :param text_data: The `text_data` parameter is a string that contains the data received from the
        WebSocket connection. In this case, it is expected to be a JSON string
        """
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]

        # Broadcast the received message to the chat channel
        await self.channel_layer.group_send(
            self.channel_name, {"type": "chat_message", "message": message}
        )

    async def chat_message(self, event):
        """
        The function `chat_message` sends a chat message to the client.
        
        :param event: The `event` parameter is a dictionary that contains information about the chat
        message event. It typically includes details such as the sender of the message, the content of
        the message, and any other relevant information. In this code snippet, the `event` dictionary is
        expected to have a key called "message
        """
        message = event["message"]

        await self.send(text_data=json.dumps({"message": message}))
