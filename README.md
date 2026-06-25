# bmad_together

A Django platform that turns [BMAD](https://github.com/bmad-code-org/BMAD-METHOD)
artifacts (briefs, PRDs, architecture docs, epics, stories, QA gates, …) into
first-class, multi-tenant database records with a REST API and a web UI — and lets
coding tools (Claude Code, Codex, OpenCode, Amp) read and write those artifacts
through the platform instead of loose markdown files.

The aim is to make BMAD produce **meaningful, queryable, governed documentation
after the fact**, scoped per user / team / organization.

## Status

Planning. See **[docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)** for the
full design: domain model, data model, REST API, web UI, and the per-tool plugin
layer.

## At a glance

- **Backend**: Django 5 + Django REST Framework, PostgreSQL (JSONB).
- **UI**: Django templates + HTMX.
- **Auth**: django-allauth (local + Google/GitHub SSO); **invite-only** org membership.
- **Tenancy**: shared DB with row-level org / team / owner scoping.
- **Artifacts**: every document is versioned (whole-document immutable snapshots).
- **API auth**: JWT for interactive clients, personal access tokens for the CLI.
- **Plugins**: REST-based per-tool scripts (a `bmadt` CLI client) generated for
  Claude Code, Codex, OpenCode, and Amp.
