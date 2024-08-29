from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
import json
from .models import ChatRooms, ChatMessages
from django.contrib.auth.models import User


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.room_group_name = f'chat_{self.chat_id}'

        # Odaya katıl
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        messages = await self.get_previous_messages(self.chat_id)

        if messages:
            for message in messages:
                username = await self.get_username(message.sender_id)
                await self.send(text_data=json.dumps({
                    'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'message': message.message,
                    'username': username
                }))

    async def disconnect(self, close_code):
        # Odadan ayrıl
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message')
        username = data.get('username')

        if message and username:
            # Mesajı kaydet ve gruba yayınla
            user, message_obj = await self.save_message(username, self.chat_id, message)
            if user and message_obj:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'created_at': message_obj.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'message': message_obj.message,
                        'username': user.username
                    }
                )

    async def chat_message(self, event):
        message = event['message']
        username = event['username']
        # Mesajı gönder
        await self.send(text_data=json.dumps({
            'message': message,
            'username': username
        }))

    @sync_to_async
    def save_message(self, username, chat_id, message):
        room = ChatRooms.objects.get(chat_id=chat_id)
        user = User.objects.get(username=username)
        message_obj = ChatMessages.objects.create(sender=user, room=room, message=message, type='normal')
        return user, message_obj

    @sync_to_async
    def get_previous_messages(self, chat_id):
        room = ChatRooms.objects.get(chat_id=chat_id)
        return list(ChatMessages.objects.filter(room=room).order_by('created_at'))

    @sync_to_async
    def get_username(self, user_id):
        return User.objects.get(id=user_id).username
