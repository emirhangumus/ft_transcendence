from app.models import Friendships
from django.contrib.auth.models import User
from django.db.models import Q

def getFriendState(user):
    friends = Friendships.objects.filter(Q(sender=user) | Q(receiver=user), status='accepted').values('sender', 'receiver')
    friends = [friend['sender'] if friend['receiver'] == user.id else friend['receiver'] for friend in friends]
    friendRequests = Friendships.objects.filter(receiver=user, status='pending').values('sender')
    sentFriendRequests = Friendships.objects.filter(sender=user, status='pending').values('receiver')

    friends = User.objects.filter(id__in=friends)
    friendRequests = User.objects.filter(id__in=friendRequests)
    sentFriendRequests = User.objects.filter(id__in=sentFriendRequests)
    
    return {
        'friends': friends,
        'friendRequests': friendRequests,
        'sentFriendRequests': sentFriendRequests
    }
    
def getFriends(user):
    friends = Friendships.objects.filter(Q(sender=user) | Q(receiver=user), status='accepted').values('sender', 'receiver')
    friends = [friend['sender'] if friend['receiver'] == user.id else friend['receiver'] for friend in friends]
    friends = User.objects.filter(id__in=friends)
    return friends