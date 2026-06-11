from django.contrib import admin
from .models import ChatSession, ChatMessage


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ("role", "agent_type", "content", "created_at", "recommended_product_ids")
    can_delete = False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display  = ("user", "title", "get_message_count", "created_at", "updated_at")
    list_filter   = ("created_at",)
    search_fields = ("user__username", "title")
    inlines       = [ChatMessageInline]

    def get_message_count(self, obj):
        return obj.messages.count()
    get_message_count.short_description = "Messages"


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display  = ("session", "role", "agent_type", "content_preview", "created_at")
    list_filter   = ("role", "agent_type")

    def content_preview(self, obj):
        return obj.content[:80]
    content_preview.short_description = "Content"
