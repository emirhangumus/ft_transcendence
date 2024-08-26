from django.db import models
from django.conf import settings
from django.core.validators import MinLengthValidator, MaxLengthValidator

# Create your models here.
class Accounts(models.Model):
    id = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True, unique=True)
    bio = models.TextField(default='')
    profile_picture_url = models.TextField(default='/static/images/default_profile_picture.png')
    status = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts'

class ChatRooms(models.Model):
    id = models.BigAutoField(primary_key=True)
    chat_id = models.CharField(
        max_length=6,
        validators=[MinLengthValidator(6)],
        null=False,
        blank=False
    )
    name = models.TextField(
        validators=[MaxLengthValidator(100)],
        null=False,
        blank=False
    )
    can_leave = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'chat_rooms'

class ChatMessages(models.Model):
    MESSAGE_TYPES = [
        ('normal', 'Normal'),
        ('friend_request', 'Friend Request'),
        ('match_invite', 'Match Invite'),
    ]

    id = models.BigAutoField(primary_key=True)
    room = models.ForeignKey(ChatRooms, models.DO_NOTHING)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, models.DO_NOTHING)
    message = models.TextField()
    replied_message = models.ForeignKey('self', models.DO_NOTHING, db_column='replied_message', blank=True, null=True)
    type = models.CharField(max_length=20, choices=MESSAGE_TYPES)
    payload = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'chat_messages'

class ChatUsers(models.Model):
    id = models.BigAutoField(primary_key=True)
    room = models.ForeignKey(ChatRooms, models.DO_NOTHING)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.DO_NOTHING)

    class Meta:
        db_table = 'chat_users'

class Friendships(models.Model):
    STATUS_TYPES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, models.DO_NOTHING, related_name='friendships_sender_set')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, models.DO_NOTHING, related_name='friendships_receiver_set')
    status = models.CharField(max_length=20, choices=STATUS_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'friendships'