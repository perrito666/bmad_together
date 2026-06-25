"""Seed a demo organization, team, user, project and a small BMAD backlog.

    python manage.py seed_demo [--email demo@example.com] [--password demo]

Idempotent: re-running updates the same demo records rather than duplicating.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import APIToken, Membership, Organization, Role, Team
from apps.artifacts.models import Artifact, ArtifactType
from apps.projects.bmad_io import import_tree
from apps.projects.models import Project

User = get_user_model()

DEMO_DOCS = {
    "core-config.yaml": "prd:\n  file: docs/prd.md\n  sharded: true\n",
    "docs/brief.md": "# Project Brief\n\nA demo BMAD workspace.",
    "docs/prd.md": (
        "# PRD\n\n## Epic 1: Onboarding\n\nLet users join.\n\n"
        "## Epic 2: Artifacts\n\nManage BMAD documents.\n"
    ),
    "docs/stories/1.1.story.md": (
        "# Story 1.1: Accept an invitation\n\n## Status\n\nApproved\n\n"
        "## Acceptance Criteria\n\n- A invited user can join an org\n"
    ),
    "docs/stories/1.2.story.md": (
        "# Story 1.2: Switch organizations\n\n## Status\n\nDraft\n"
    ),
}


class Command(BaseCommand):
    help = "Seed a demo org/team/user/project with a small BMAD backlog."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="demo@example.com")
        parser.add_argument("--password", default="demo")

    @transaction.atomic
    def handle(self, *args, **opts):
        email = opts["email"]
        user, created = User.objects.get_or_create(
            email=email, defaults={"username": email.split("@")[0]}
        )
        user.set_password(opts["password"])
        user.save()

        org, _ = Organization.objects.get_or_create(slug="demo", defaults={"name": "Demo Org"})
        team, _ = Team.objects.get_or_create(
            organization=org, slug="core", defaults={"name": "Core Team"}
        )
        Membership.objects.get_or_create(
            user=user, organization=org, team=None, defaults={"role": Role.OWNER}
        )
        project, _ = Project.objects.get_or_create(
            organization=org, slug="demo-app",
            defaults={"name": "Demo App", "owner": user, "team": team},
        )

        summary = import_tree(project, DEMO_DOCS, author=user)
        # Stamp the brief as published so the dashboard shows a non-draft.
        Artifact.objects.filter(project=project, type=ArtifactType.BRIEF).update(status="published")

        token, raw = APIToken.issue(user=user, name="demo-cli")

        self.stdout.write(self.style.SUCCESS("Demo data ready:"))
        self.stdout.write(f"  login:      {email} / {opts['password']}")
        self.stdout.write(f"  org/team:   {org.slug}/{team.slug}")
        self.stdout.write(f"  project_id: {project.id}")
        self.stdout.write(f"  imported:   {summary.as_dict()}")
        self.stdout.write(f"  API token:  {raw}")
        self.stdout.write("  (export BMADT_TOKEN=<token> to use the bmadt CLI)")
