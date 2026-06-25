"""Accounts: users, organizations, teams, memberships, invitations, API tokens.

Membership is invite-only: orgs are provisioned by staff, and users join exclusively
by accepting an Invitation (which creates their Membership).
"""
from __future__ import annotations

import secrets
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Role(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"
    VIEWER = "viewer", "Viewer"


# Rank for "role >= required" checks. Higher means more privilege.
ROLE_RANK = {Role.VIEWER: 0, Role.MEMBER: 1, Role.ADMIN: 2, Role.OWNER: 3}


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self) -> str:
        return self.email


class Organization(UUIDModel):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Team(UUIDModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="teams"
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "slug"], name="uniq_team_slug_per_org"
            )
        ]

    def __str__(self) -> str:
        return f"{self.organization.slug}/{self.slug}"


class Membership(UUIDModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="memberships", null=True, blank=True
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organization", "team"], name="uniq_membership"
            )
        ]

    def __str__(self) -> str:
        scope = self.team or self.organization
        return f"{self.user} @ {scope} ({self.role})"

    def has_role(self, required: str) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[required]


class InvitationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    REVOKED = "revoked", "Revoked"
    EXPIRED = "expired", "Expired"


def _default_invite_expiry():
    return timezone.now() + timezone.timedelta(days=getattr(settings, "INVITE_TTL_DAYS", 7))


class Invitation(UUIDModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invitations"
    )
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="invitations", null=True, blank=True
    )
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    token = models.CharField(max_length=64, unique=True, default=secrets.token_urlsafe)
    status = models.CharField(
        max_length=20, choices=InvitationStatus.choices, default=InvitationStatus.PENDING
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_invitations",
    )
    expires_at = models.DateTimeField(default=_default_invite_expiry)

    def __str__(self) -> str:
        return f"invite {self.email} -> {self.organization.slug} ({self.status})"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def is_acceptable(self) -> bool:
        return self.status == InvitationStatus.PENDING and not self.is_expired


class APIToken(UUIDModel):
    """Personal access token for the bmadt CLI / automation.

    Only the hashed key is stored. The raw token (``prefix.secret``) is shown once
    at creation time. ``scopes`` is reserved for future per-project/read-only refinement.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_tokens"
    )
    name = models.CharField(max_length=100)
    prefix = models.CharField(max_length=12, db_index=True)
    hashed_key = models.CharField(max_length=128)
    scopes = models.JSONField(default=list, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        state = "revoked" if self.revoked_at else "active"
        return f"{self.name} ({self.prefix}…, {state})"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    @staticmethod
    def _hash(raw_secret: str) -> str:
        import hashlib

        return hashlib.sha256(raw_secret.encode()).hexdigest()

    @classmethod
    def issue(cls, *, user, name: str) -> tuple[APIToken, str]:
        """Create a token, returning (instance, raw_token). Raw token shown once."""
        prefix = "bmadt_" + secrets.token_hex(3)
        secret = secrets.token_urlsafe(32)
        token = cls.objects.create(
            user=user, name=name, prefix=prefix, hashed_key=cls._hash(secret)
        )
        return token, f"{prefix}.{secret}"
