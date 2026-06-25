"""Template helpers: safe markdown rendering + small formatting utilities."""
import bleach
import markdown as md
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS) | {
    "p", "pre", "h1", "h2", "h3", "h4", "h5", "h6", "br", "hr", "span", "div",
    "table", "thead", "tbody", "tr", "th", "td", "img",
}
_ALLOWED_ATTRS = {
    "*": ["class"],
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title"],
}


@register.filter
def render_markdown(text: str):
    """Render markdown to sanitized HTML."""
    if not text:
        return ""
    html = md.markdown(text, extensions=["fenced_code", "tables", "sane_lists"])
    cleaned = bleach.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)
    return mark_safe(cleaned)  # noqa: S308 - bleach-sanitized above


@register.filter
def pretty_json(value):
    import json

    try:
        return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


@register.filter
def status_class(status: str) -> str:
    """A CSS class slug for a story/artifact status badge."""
    return f"badge--{(status or 'unknown').replace('_', '-')}"
