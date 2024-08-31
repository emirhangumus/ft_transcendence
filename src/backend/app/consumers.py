from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
import json
from .models import ChatRooms, ChatMessages
from django.contrib.auth.models import User
from .logic import PongGame
import threading
import time
from .jwt import PingPongObtainPairSerializer, validate_access_token, validate_refresh_token
import asyncio

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


def gameTread(self, game):
    while True:
        game.update()
        print("thread")
        time.sleep(1)
        if game.end_game() or game.timeout():
            break

def cookieParser(cookie):
    cookies = {}
    for c in cookie.decode().split('; '):
        key, value = c.split('=')
        cookies[key] = value
    return cookies

def findCookie(scope):
    for header in scope['headers']:
        if header[0] == b'cookie':
            return cookieParser(header[1])

game_rooms = {}

class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print(game_rooms)
        cookies = findCookie(self.scope)
        if not cookies:
            await self.close()
            return
        user_payload = cookies['access_token']
        if not user_payload:
            await self.close()
            return
        user_data = validate_access_token(user_payload)
        if user_data and user_data['valid']:
            self.game_id = self.scope['url_route']['kwargs']['game_id']
            self.room_group_name = f'game_{self.game_id}'

            # if there is already two players in the room
            print(game_rooms)
            print(self.room_group_name)
            if self.room_group_name not in game_rooms:
                print("room exists")
                await self.close()
                return
            
            if game_rooms.get(self.room_group_name) and not game_rooms[self.room_group_name].get('player1'):
                game_rooms[self.room_group_name]['player1'] = {
                    'self': self,
                    'user': user_data
                }
            elif game_rooms.get(self.room_group_name) and game_rooms[self.room_group_name].get('player1'):
                game_rooms[self.room_group_name]['player2'] = {
                    'self': self,
                    'user': user_data
                }

            # Odaya katıl
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            # game = PongGame(data)
            # t = threading.Thread(target=self.gameTread, daemon=True, args=[game])

            await self.accept()
            asyncio.create_task(self.stream_data())
        else:
            await self.close()

    async def disconnect(self, close_code):
        # Odadan ayrıl
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        
        if data['type'] == 'move':
            if self.channel_name == game_rooms[self.room_group_name]['player1']['self'].channel_name:
                game_rooms[self.room_group_name]['game'].move_player(data['direction'])
            elif self.channel_name == game_rooms[self.room_group_name]['player2']['self'].channel_name:
                game_rooms[self.room_group_name]['game'].player2_move(data['direction'])

    async def stream_data(self):
        while True:
            current_time = time.time()
            # Generate or fetch your game data to stream
            game_data = {
                'type': 'game_update',
                'payload': {
                    'timestamp': current_time.__str__(),
                    'data': game_rooms[self.room_group_name]['game'].get_game_data()
                    # 'data': self.channel_layer.group_channels[self.room_group_name]
                    # Add other game-related data
                }
            }

            # Broadcast the data to the room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'game_data',
                    'message': game_data
                }
            )

            # Wait for a specific interval before sending the next update
            await asyncio.sleep(0.05)  # Adjust the interval as needed | 0.05 is 20 FPS
            
    async def game_data(self, event):
        # Send the game data to WebSocket
        await self.send(text_data=json.dumps(event['message']))