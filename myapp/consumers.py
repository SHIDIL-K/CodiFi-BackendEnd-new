from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import ChatRoom, Message

User = get_user_model()


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """
    Real-time chat consumer for course communication.
    Authenticated via TokenAuthMiddlewareStack using JWT in query string.
    """

    async def connect(self):
        self.chatroom_id = self.scope["url_route"]["kwargs"]["chatroom_id"]
        self.user = self.scope.get("user")

        # Reject if unauthenticated
        if not self.user or not self.user.is_authenticated:
            print("❌ Unauthorized connection attempt")
            await self.close()
            return

        # Check if user belongs to this chatroom
        allowed = await self._is_user_in_chat(self.user.id, self.chatroom_id)
        if not allowed:
            print(f"❌ Access denied for user {self.user.id} to chatroom {self.chatroom_id}")
            await self.close()
            return

        # Join group
        self.group_name = f"chat_{self.chatroom_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        print(f"✅ {self.user.username} connected to chatroom {self.chatroom_id}")

        # Send chat history
        history = await self._get_messages(self.chatroom_id)
        await self.send_json({"type": "chat_history", "messages": history})

    async def disconnect(self, close_code):
        """Remove user from the chat group when disconnected."""
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        print(f"⚠️ {getattr(self.user, 'username', 'Anonymous')} disconnected from chat {self.chatroom_id}")

    async def receive_json(self, content):
        """Receive a message from the WebSocket and broadcast it."""
        text = (content.get("message") or "").strip()
        if not text or not self.user.is_authenticated:
            return

        msg = await self._save_message(self.chatroom_id, self.user.id, text)

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat_message",
                "message": msg["content"],
                "sender": msg["sender"],
                "timestamp": msg["timestamp"],
            },
        )

    async def chat_message(self, event):
        """Send a broadcast message to WebSocket clients."""
        await self.send_json(event)

    # ==========================================================
    # 🗂️ Database Helpers (async-safe)
    # ==========================================================

    @database_sync_to_async
    def _is_user_in_chat(self, user_id, chatroom_id):
        """Check if a user is part of this chatroom."""
        try:
            chat = ChatRoom.objects.select_related("student", "instructor").get(pk=chatroom_id)
            return chat.student_id == user_id or chat.instructor_id == user_id
        except ChatRoom.DoesNotExist:
            return False

    @database_sync_to_async
    def _get_messages(self, chatroom_id):
        """Fetch chat history."""
        msgs = Message.objects.filter(chatroom_id=chatroom_id).order_by("timestamp")
        return [
            {
                "sender": m.sender.username,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in msgs
        ]

    @database_sync_to_async
    def _save_message(self, chatroom_id, user_id, text):
        """Persist a message to the database."""
        user = User.objects.get(pk=user_id)
        chat = ChatRoom.objects.get(pk=chatroom_id)
        msg = Message.objects.create(chatroom=chat, sender=user, content=text)
        return {
            "sender": user.username,
            "content": msg.content,
            "timestamp": msg.timestamp.isoformat(),
        }
