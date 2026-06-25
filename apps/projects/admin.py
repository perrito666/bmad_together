from django.contrib import admin

from .models import CoreConfig, Project, SprintStatus


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "organization", "team", "owner")
    list_filter = ("organization",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("organization", "team", "owner")


@admin.register(CoreConfig)
class CoreConfigAdmin(admin.ModelAdmin):
    list_display = ("project",)


@admin.register(SprintStatus)
class SprintStatusAdmin(admin.ModelAdmin):
    list_display = ("project",)
