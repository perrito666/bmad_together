from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("healthz", views.healthz, name="healthz"),
    path("", views.dashboard, name="dashboard"),
    path("set-org/", views.set_org, name="set_org"),
    path("projects/<uuid:pk>/", views.project_detail, name="project_detail"),
    path("projects/<uuid:pk>/board/", views.board, name="board"),
    path("artifacts/<uuid:pk>/", views.artifact_detail, name="artifact_detail"),
    path("artifacts/<uuid:pk>/edit/", views.artifact_edit, name="artifact_edit"),
    path("artifacts/<uuid:pk>/diff/", views.artifact_diff, name="artifact_diff"),
    path("stories/<uuid:pk>/", views.story_detail, name="story_detail"),
    path("stories/<uuid:pk>/transition/", views.story_transition, name="story_transition"),
]
