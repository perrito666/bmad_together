from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .domain_views import (
    ArtifactViewSet,
    EpicViewSet,
    ProjectViewSet,
    StoryViewSet,
)
from .views import (
    APITokenViewSet,
    InvitationAcceptView,
    MeView,
    OrganizationViewSet,
)

router = DefaultRouter()
router.register("orgs", OrganizationViewSet, basename="org")
router.register("auth/tokens", APITokenViewSet, basename="apitoken")
router.register("projects", ProjectViewSet, basename="project")
router.register("artifacts", ArtifactViewSet, basename="artifact")
router.register("epics", EpicViewSet, basename="epic")
router.register("stories", StoryViewSet, basename="story")

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
