from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
import json
from .models import ChatRooms, ChatMessages
from django.contrib.auth.models import User
#from ../users.model import User, Friend
import random
import string

def randomId():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_id = randomId()
        self.room_group_name = f'chat_{self.chat_id}'
        # Odayı oluştur veya getir
        # Odaya katıl
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

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

        if message:
            # Mesajı kaydet ve gruba yayınla
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'username': username
                }
            )

    async def chat_message(self, event):
        message = event['message']
        username = event['username']

       

    @sync_to_async
    def get_chat_room(self, chat_id):
        return ChatRooms.objects.get(chat_id=chat_id)

    @sync_to_async
    def save_message(self, username, chat_id, message):
        room = self.get_chat_room(chat_id=chat_id)
        user = User.objects.get(username=username)
        if not room or not user:
            return
        ChatMessages.objects.create(sender=user, room=room, message=message, type='normal')

    @sync_to_async
    def get_previous_messages(self, chat_id):
        try:
            room = self.get_chat_room(chat_id=chat_id)
            return list(ChatMessages.objects.filter(room=room).order_by('created_at'))
        except ChatRooms.DoesNotExist:
            return []
