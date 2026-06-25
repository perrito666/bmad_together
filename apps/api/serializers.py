from rest_framework import serializers

from apps.accounts.models import APIToken, Invitation, Membership, Organization, Team


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ("id", "name", "slug", "created_at")


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ("id", "organization", "name", "slug", "created_at")
        read_only_fields = ("organization",)


class MembershipSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Membership
        fields = ("id", "user", "email", "organization", "team", "role")


class MeSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    username = serializers.CharField()
    memberships = MembershipSerializer(many=True)


class InvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = (
            "id", "organization", "team", "email", "role", "status", "expires_at",
        )
        read_only_fields = ("organization", "status", "expires_at")


class APITokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = APIToken
        fields = ("id", "name", "prefix", "last_used_at", "revoked_at", "created_at")
        read_only_fields = ("prefix", "last_used_at", "revoked_at", "created_at")


class APITokenCreateResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    prefix = serializers.CharField()
    token = serializers.CharField(help_text="Raw token, shown only once.")
