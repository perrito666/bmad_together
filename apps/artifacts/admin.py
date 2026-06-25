from django.contrib import admin

from apps.core.models import Version

from .models import Artifact, Attachment


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0


@admin.register(Artifact)
class ArtifactAdmin(admin.ModelAdmin):
    list_display = ("title", "type", "status", "project", "updated_at")
    list_filter = ("type", "status", "project")
    search_fields = ("title", "slug")
    inlines = [AttachmentInline]


@admin.register(Version)
class VersionAdmin(admin.ModelAdmin):
    list_display = ("content_type", "object_id", "number", "author", "created_at")
    list_filter = ("content_type",)
