from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import (
    APIToken,
    Invitation,
    InvitationStatus,
    Membership,
    Organization,
    Role,
    Team,
)
from apps.accounts.scoping import accessible_org_ids, user_role_in_org

from .serializers import (
    APITokenCreateResponseSerializer,
    APITokenSerializer,
    InvitationSerializer,
    MembershipSerializer,
    MeSerializer,
    OrganizationSerializer,
    TeamSerializer,
)


class MeView(APIView):
    def get(self, request):
        user = request.user
        data = {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "memberships": Membership.objects.filter(user=user).select_related(
                "organization", "team"
            ),
        }
        return Response(MeSerializer(data).data)


class APITokenViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Manage the caller's personal access tokens. DELETE revokes (soft)."""

    serializer_class = APITokenSerializer

    def get_queryset(self):
        return APIToken.objects.filter(user=self.request.user).order_by("-created_at")

    def create(self, request, *args, **kwargs):
        name = request.data.get("name", "").strip()
        if not name:
            return Response(
                {"detail": "name is required.", "code": "invalid"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        token, raw = APIToken.issue(user=request.user, name=name)
        body = {"id": token.id, "name": token.name, "prefix": token.prefix, "token": raw}
        return Response(
            APITokenCreateResponseSerializer(body).data, status=status.HTTP_201_CREATED
        )

    def perform_destroy(self, instance):
        instance.revoked_at = timezone.now()
        instance.save(update_fields=["revoked_at"])


class OrganizationViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Read-only over orgs the caller belongs to. Org creation is staff-only (admin)."""

    serializer_class = OrganizationSerializer

    def get_queryset(self):
        return Organization.objects.filter(id__in=accessible_org_ids(self.request.user))

    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        org = self.get_object()
        qs = Membership.objects.filter(organization=org).select_related("user", "team")
        return Response(MembershipSerializer(qs, many=True).data)

    @action(detail=True, methods=["get", "post"])
    def teams(self, request, pk=None):
        org = self.get_object()
        if request.method == "GET":
            qs = Team.objects.filter(organization=org)
            return Response(TeamSerializer(qs, many=True).data)
        self._require_role(org, Role.ADMIN)
        ser = TeamSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save(organization=org)
        return Response(ser.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post"])
    def invitations(self, request, pk=None):
        org = self.get_object()
        if request.method == "GET":
            qs = Invitation.objects.filter(organization=org)
            return Response(InvitationSerializer(qs, many=True).data)
        self._require_role(org, Role.ADMIN)
        ser = InvitationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        invite = ser.save(organization=org, invited_by=request.user)
        self._send_invite(request, invite)
        return Response(InvitationSerializer(invite).data, status=status.HTTP_201_CREATED)

    def _require_role(self, org, required):
        from rest_framework.exceptions import PermissionDenied

        from apps.accounts.models import ROLE_RANK

        role = user_role_in_org(self.request.user, org.id)
        if role is None or ROLE_RANK[role] < ROLE_RANK[required]:
            raise PermissionDenied("Insufficient role for this action.")

    @staticmethod
    def _send_invite(request, invite):
        from django.conf import settings
        from django.core.mail import send_mail

        link = request.build_absolute_uri(f"/api/v1/invitations/{invite.token}/accept/")
        send_mail(
            subject="You've been invited to bmad_together",
            message=f"Accept your invitation: {link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invite.email],
            fail_silently=True,
        )


class InvitationAcceptView(APIView):
    permission_classes = [AllowAny]  # token in URL is the credential; user must be authed

    def post(self, request, token):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required to accept an invite.", "code": "unauth"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        invite = get_object_or_404(Invitation, token=token)
        if invite.is_expired and invite.status == InvitationStatus.PENDING:
            invite.status = InvitationStatus.EXPIRED
            invite.save(update_fields=["status"])
        if not invite.is_acceptable():
            return Response(
                {"detail": f"Invitation is {invite.status}.", "code": "invite_unavailable"},
                status=status.HTTP_409_CONFLICT,
            )
        membership, _created = Membership.objects.get_or_create(
            user=request.user,
            organization=invite.organization,
            team=invite.team,
            defaults={"role": invite.role},
        )
        invite.status = InvitationStatus.ACCEPTED
        invite.save(update_fields=["status"])
        return Response(MembershipSerializer(membership).data, status=status.HTTP_200_OK)
