from rest_framework.pagination import CursorPagination


class TimestampCursorPagination(CursorPagination):
    """Cursor pagination ordered by our standard ``created_at`` timestamp."""

    ordering = "-created_at"
    page_size = 25
