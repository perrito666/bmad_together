from django.contrib import admin

from .models import Epic, Story


class StoryInline(admin.TabularInline):
    model = Story
    extra = 0
    fields = ("number", "title", "status", "assignee")
    show_change_link = True


@admin.register(Epic)
class EpicAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "project", "status")
    list_filter = ("project", "status")
    search_fields = ("title",)
    inlines = [StoryInline]


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ("label", "title", "status", "assignee")
    list_filter = ("status", "epic__project")
    search_fields = ("title",)

    @admin.display(description="Story")
    def label(self, obj):
        return obj.label
