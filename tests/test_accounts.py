import pytest
from rest_framework.test import APIClient

from apps.accounts.factories import (
    MembershipFactory,
    OrganizationFactory,
    UserFactory,
)
from apps.accounts.models import APIToken, Invitation, Membership, Role

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


def test_pat_issue_and_authenticate(client):
    user = UserFactory()
    token, raw = APIToken.issue(user=user, name="laptop")
    assert raw.startswith("bmadt_")
    assert "." in raw

    client.credentials(HTTP_AUTHORIZATION=f"Token {raw}")
    resp = client.get("/api/v1/auth/me/")
    assert resp.status_code == 200
    assert resp.data["email"] == user.email


def test_pat_revoked_rejected(client):
    user = UserFactory()
    token, raw = APIToken.issue(user=user, name="ci")
    from django.utils import timezone

    token.revoked_at = timezone.now()
    token.save()
    client.credentials(HTTP_AUTHORIZATION=f"Token {raw}")
    assert client.get("/api/v1/auth/me/").status_code == 401


def test_me_lists_memberships(client):
    m = MembershipFactory(role=Role.ADMIN)
    client.force_authenticate(m.user)
    resp = client.get("/api/v1/auth/me/")
    assert resp.status_code == 200
    assert len(resp.data["memberships"]) == 1
    assert resp.data["memberships"][0]["role"] == Role.ADMIN


def test_orgs_scoped_to_memberships(client):
    member = MembershipFactory()
    OrganizationFactory()  # an org the user is NOT in
    client.force_authenticate(member.user)
    resp = client.get("/api/v1/orgs/")
    ids = {row["id"] for row in resp.data["results"]}
    assert str(member.organization_id) in ids
    assert len(ids) == 1


def test_admin_can_invite_and_user_accepts(client):
    admin = MembershipFactory(role=Role.ADMIN)
    org = admin.organization
    client.force_authenticate(admin.user)

    resp = client.post(
        f"/api/v1/orgs/{org.id}/invitations/",
        {"email": "newbie@example.com", "role": Role.MEMBER},
        format="json",
    )
    assert resp.status_code == 201
    invite = Invitation.objects.get(email="newbie@example.com")

    newbie = UserFactory(email="newbie@example.com")
    client.force_authenticate(newbie)
    accept = client.post(f"/api/v1/invitations/{invite.token}/accept/")
    assert accept.status_code == 200
    assert Membership.objects.filter(user=newbie, organization=org).exists()
    invite.refresh_from_db()
    assert invite.status == "accepted"


def test_member_cannot_invite(client):
    member = MembershipFactory(role=Role.MEMBER)
    client.force_authenticate(member.user)
    resp = client.post(
        f"/api/v1/orgs/{member.organization_id}/invitations/",
        {"email": "x@example.com"},
        format="json",
    )
    assert resp.status_code == 403


def test_unauthenticated_cannot_accept(client):
    member = MembershipFactory(role=Role.ADMIN)
    invite = Invitation.objects.create(
        organization=member.organization, email="z@example.com", invited_by=member.user
    )
    resp = client.post(f"/api/v1/invitations/{invite.token}/accept/")
    assert resp.status_code == 401
