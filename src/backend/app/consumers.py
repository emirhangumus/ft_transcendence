from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
import json
from .models import ChatRooms, ChatMessages, ChatUsers, Notifications
from django.contrib.auth.models import User
import time
import asyncio
from .utils import checkAuthForWS
from .managers import NotificationManager, TournamentManager

game_rooms = {}
user_room_pairs = {}
notificationManager = NotificationManager()
tournamentManager = TournamentManager()

class ChatConsumer(AsyncWebsocketConsumer):
    user_data = {}
    
    async def connect(self):
        user_data = checkAuthForWS(self.scope)
        if user_data and user_data['valid']:
            self.user_data = user_data
            self.chat_id = self.scope['url_route']['kwargs']['chat_id']
            self.room_group_name = f'chat_{self.chat_id}'

            # Odaya katıl
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )

            # if the user is in user_room_pairs, remove it
            if self.room_group_name in user_room_pairs:
                try:
                    index = user_room_pairs[self.room_group_name].index(user_data['user_id'])
                    del user_room_pairs[self.room_group_name][index]
                except ValueError:
                    pass
            await self.accept()
            user_room_pairs[self.room_group_name] = user_room_pairs.get(self.room_group_name, [])
            user_room_pairs[self.room_group_name].append(user_data['user_id'])

            messages = await self.get_previous_messages(self.chat_id)
            print("oooo->" ,user_room_pairs)
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
        if self.room_group_name in user_room_pairs:
            try:
                index = user_room_pairs[self.room_group_name].index(self.user_data['user_id'])
                del user_room_pairs[self.room_group_name][index]
            except ValueError:
                pass

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message')
        username = data.get('username')

        if message and username:
            # Mesajı kaydet ve gruba yayınla
            user, message_obj = await self.save_message(username, self.chat_id, message)
            users_that_are_in_chat = await self.get_users_in_chat(self.chat_id)
            for chat_user in users_that_are_in_chat:
                if chat_user['user_id'] != user.id and not self.is_user_in_channel(chat_user['user_id']):
                    print("->", user_room_pairs)
                    print("->", self.is_user_in_channel(chat_user['user_id']))
                    notificationManager.add_notification(chat_user['user_id'], f'{user.username} sent a message to chat {self.chat_id}')
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
        
    def is_user_in_channel(self, user_id):
        for room in user_room_pairs:
            if user_id in user_room_pairs[room]:
                return True
        return False

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
    
    @sync_to_async
    def get_users_in_chat(self, chat_id):
        room = ChatRooms.objects.get(chat_id=chat_id)
        return list(ChatUsers.objects.filter(room=room).values('user_id'))

class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user_data = checkAuthForWS(self.scope)
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
                game_rooms[self.room_group_name]['game'].move_player2(data['direction'])

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

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.check_notification_manager()
        user_data = checkAuthForWS(self.scope)
        if user_data and user_data['valid']:
            self.user_id = user_data['user_id']
            self.room_group_name = f'notifications_{self.user_id}'
            # Odaya katıl
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()
            notificationManager.register_user(self, self.user_id)
            notifications = await self.get_notifications(self.user_id, 'no')
            for notification in notifications:
                message = notification.payload.get('message')
                notificationManager.add_notification(self.user_id, message, notification.payload, notification.type, False)
        else:
            await self.close()
            
    def check_notification_manager(self):
        notificationManager.start()
        tournamentManager.start()

    async def disconnect(self, close_code):
        # Odadan ayrıl
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        notificationManager.unregister_user(self.user_id)
        
    async def receive(self, text_data):
        data = json.loads(text_data)
        if data['type'] == 'clear':
            await notificationManager.mark_as_read_all(self.user_id)

    @sync_to_async
    def get_notifications(self, user_id, is_read='all'):
        if is_read == 'all':
            notifications = Notifications.objects.filter(receiver=user_id)
        else:
            if is_read == 'yes':
                is_read = True
            else:
                is_read = False
            notifications = Notifications.objects.filter(receiver=user_id, is_read=is_read)
        return list(notifications)

class TournamentConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user_data = checkAuthForWS(self.scope)
        if user_data and user_data['valid']:
            self.tournament_id = self.scope['url_route']['kwargs']['tournament_id']
            self.room_group_name = f'tournament_{self.tournament_id}'

            # Odaya katıl
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()
            user = await self.get_user(user_data['user_id'])
            if user:
                self.user_id = user.id
                tournamentManager.add_player(self.tournament_id, user, self)
        else:
            await self.close()

    async def disconnect(self, close_code):
        # Odadan ayrıl
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        user = await self.get_user(self.user_id)
        tournamentManager.remove_player(self.tournament_id, user)

    async def receive(self, text_data):
        data = json.loads(text_data)
        print(data)
    
    @sync_to_async
    def get_user(self, user_id):
        return User.objects.get(id=user_id)