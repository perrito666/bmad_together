from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    APITokenViewSet,
    InvitationAcceptView,
    MeView,
    OrganizationViewSet,
)

router = DefaultRouter()
router.register("orgs", OrganizationViewSet, basename="org")
router.register("auth/tokens", APITokenViewSet, basename="apitoken")

urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", MeView.as_view(), name="me"),
    path(
        "invitations/<str:token>/accept/",
        InvitationAcceptView.as_view(),
        name="invitation-accept",
    ),
    path("", include(router.urls)),
]
