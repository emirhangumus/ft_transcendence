from app.models import ChatRooms, ChatUsers, ChatMessages, Friendships
from django.contrib.auth.models import User
from django.db.models import Q
from ..utils import generateRandomID

def assignChatbotRoom(userId):
    BOT_ID = 1
    chatbot = User.objects.get(id=BOT_ID)
    chatroom = ChatRooms.objects.create(
        chat_id=generateRandomID('chatrooms'),
        name='chat.botRoom',
        can_leave=False
    )
    ChatUsers.objects.create(
        room=chatroom,
        user=chatbot
    )
    ChatUsers.objects.create(
        room=chatroom,
        user=userId
    )
    ChatMessages.objects.create(
        room=chatroom,
        sender=chatbot,
        message='Oyuna hoşgelmişsiniz. Ben ClapTrap Pipe.',
        type='normal'
    )
    return chatroom.id

def getChatRooms(userId):
    chatRooms = ChatUsers.objects.filter(user=userId).values('room')
    chatRooms = ChatRooms.objects.filter(id__in=chatRooms)
    return chatRooms

def getChatRoom(userId, chatId):
    chatRoom = ChatRooms.objects.filter(chat_id=chatId)
    if chatRoom:
        chatRoom = ChatUsers.objects.filter(user=userId, room=chatRoom[0].id)
        if chatRoom:
            return chatRoom[0]
    return None

def getChatMessages(roomId, limit):
    chatMessages = ChatMessages.objects.filter(room=roomId).order_by('-created_at')[:limit]
    return chatMessages

# `users` is a list of username
def createChatRoom(name, createdUser, users, can_leave=True):
    # check every user is friend with the createdUser
    userObjects = []
    for user in users:
        u = User.objects.filter(username=user).first()
        if not u:
            return None
        friendship = Friendships.objects.filter(Q(sender=createdUser, receiver=u) | Q(sender=u, receiver=createdUser)).first()
        if not friendship or friendship.status != 'accepted':
            return None
        userObjects.append(u)
    
    chatRoom = ChatRooms(name=name, chat_id=generateRandomID('chatrooms'), can_leave=can_leave)
    chatRoom.save()
    ChatUsers(user=createdUser, room=chatRoom).save()
    for user in userObjects:
        chatUser = ChatUsers(user=user, room=chatRoom)
        chatUser.save()
    return chatRoom

def leaveChatRoom(roomId, userId):
    chatRoom = ChatRooms.objects.filter(id=roomId).first()
    if not chatRoom:
        return False
    chatUsers = ChatUsers.objects.filter(user=userId, room=chatRoom)
    # remove user and if there is only one user left, delete the chat room
    if chatUsers:
        chatUsers.delete()
        if ChatUsers.objects.filter(room=chatRoom).count() == 1:
            chatRoom.delete()
    return True

def deleteChatRoom(roomId):
    # delete all messages
    ChatMessages.objects.filter(room=roomId).delete()
    # delete all users
    ChatUsers.objects.filter(room=roomId).delete()
    # delete the room
    ChatRooms.objects.filter(id=roomId).delete()
    return True

def getFriendChatRooms(username1, username2):
    user1 = User.objects.filter(username=username1).first()
    user2 = User.objects.filter(username=username2).first()
    if not user1 or not user2:
        return None
    chatRoom = ChatRooms.objects.filter(can_leave=False)
    the_chat_room = None
    for room in chatRoom:
        chatUsers = ChatUsers.objects.filter(room=room)
        if chatUsers:
            if chatUsers.filter(user=user1) and chatUsers.filter(user=user2):
                the_chat_room = room
                break
    return the_chat_room