from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import APIToken, Invitation, Membership, Organization, Team, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("email", "username", "is_staff", "is_active")
    search_fields = ("email", "username")


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ("user", "team")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MembershipInline]


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "organization")
    search_fields = ("name", "slug")
    list_filter = ("organization",)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "team", "role")
    list_filter = ("role", "organization")
    autocomplete_fields = ("user", "organization", "team")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "organization", "team", "role", "status", "expires_at")
    list_filter = ("status", "organization")
    readonly_fields = ("token",)


@admin.register(APIToken)
class APITokenAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "prefix", "last_used_at", "revoked_at")
    list_filter = ("revoked_at",)
    readonly_fields = ("prefix", "hashed_key", "last_used_at")
