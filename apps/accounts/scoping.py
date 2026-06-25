"""Tenant-scoping primitives reused by all artifact viewsets (milestone 3+).

These centralize the access invariant: a user can only see rows belonging to an
organization (and, when team-scoped, a team) they hold a Membership in.
"""
from __future__ import annotations

from rest_framework import permissions

from .models import Membership, Role


def accessible_org_ids(user) -> set:
    if not user or not user.is_authenticated:
        return set()
    return set(
        Membership.objects.filter(user=user).values_list("organization_id", flat=True)
    )


def user_role_in_org(user, organization_id) -> str | None:
    """Highest role the user holds in the given organization, or None."""
    roles = Membership.objects.filter(
        user=user, organization_id=organization_id
    ).values_list("role", flat=True)
    if not roles:
        return None
    from .models import ROLE_RANK

    return max(roles, key=lambda r: ROLE_RANK[r])


class TenantScopedQuerysetMixin:
    """Filter a viewset's queryset to the requester's organizations.

    Subclasses set ``org_lookup`` to the ORM path from the model to its Organization
    (e.g. ``"organization_id"`` or ``"project__organization_id"``).
    """

    org_lookup = "organization_id"

    def get_queryset(self):
        qs = super().get_queryset()
        org_ids = accessible_org_ids(self.request.user)
        return qs.filter(**{f"{self.org_lookup}__in": org_ids})


# HTTP method -> minimum role required.
METHOD_MIN_ROLE = {
    "GET": Role.VIEWER,
    "HEAD": Role.VIEWER,
    "OPTIONS": Role.VIEWER,
    "POST": Role.MEMBER,
    "PUT": Role.MEMBER,
    "PATCH": Role.MEMBER,
    "DELETE": Role.ADMIN,
}


class RolePermission(permissions.BasePermission):
    """Object-level role gate.

    Objects must expose ``organization_id`` (directly or via a ``get_organization_id``
    helper) so we can resolve the requester's role for the object's org.
    """

    def has_object_permission(self, request, view, obj):
        from .models import ROLE_RANK

        org_id = getattr(obj, "organization_id", None)
        if org_id is None and hasattr(obj, "get_organization_id"):
            org_id = obj.get_organization_id()
        if org_id is None:
            return False
        role = user_role_in_org(request.user, org_id)
        if role is None:
            return False
        required = METHOD_MIN_ROLE.get(request.method, Role.ADMIN)
        return ROLE_RANK[role] >= ROLE_RANK[required]
