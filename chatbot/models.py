from django.db import models
from django.contrib.auth.models import User


class ChatSession(models.Model):
    """
    Represents a single conversation thread between a user and AgroSense AI.
    """
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_sessions")
    title      = models.CharField(max_length=200, default="New Conversation")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active  = models.BooleanField(default=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "is_active", "-updated_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.title}"

    def get_message_count(self):
        return self.messages.count()

    def get_last_message(self):
        return self.messages.order_by("-created_at").first()


class ChatMessage(models.Model):
    """
    A single message in a ChatSession (either user or AI).
    """
    ROLE_USER = "user"
    ROLE_AI   = "assistant"
    ROLE_CHOICES = [
        (ROLE_USER, "User"),
        (ROLE_AI,   "AI"),
    ]

    session    = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role       = models.CharField(max_length=10, choices=ROLE_CHOICES)
    agent_type = models.CharField(max_length=80, blank=True)
    content    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    # Optional: store any recommended products linked to this AI message
    recommended_product_ids = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["session", "created_at"]),
        ]

    def __str__(self):
        return f"[{self.role}] {self.content[:60]}…"
