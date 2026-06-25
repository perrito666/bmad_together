"""Personal Access Token authentication for the bmadt CLI / automation.

Clients send ``Authorization: Token <prefix>.<secret>``. We look the token up by its
indexed prefix, then compare hashes in constant time.
"""
from __future__ import annotations

import hmac

from django.utils import timezone
from rest_framework import authentication, exceptions

from .models import APIToken


class PersonalAccessTokenAuthentication(authentication.BaseAuthentication):
    keyword = "Token"

    def authenticate(self, request):
        auth = authentication.get_authorization_header(request).split()
        if not auth or auth[0].lower() != self.keyword.lower().encode():
            return None
        if len(auth) != 2:
            raise exceptions.AuthenticationFailed("Invalid token header.")

        raw = auth[1].decode()
        if "." not in raw:
            raise exceptions.AuthenticationFailed("Malformed token.")
        prefix, secret = raw.split(".", 1)

        try:
            token = APIToken.objects.select_related("user").get(prefix=prefix)
        except APIToken.DoesNotExist as exc:
            raise exceptions.AuthenticationFailed("Invalid token.") from exc

        if not token.is_active:
            raise exceptions.AuthenticationFailed("Token revoked.")
        if not hmac.compare_digest(token.hashed_key, APIToken._hash(secret)):
            raise exceptions.AuthenticationFailed("Invalid token.")
        if not token.user.is_active:
            raise exceptions.AuthenticationFailed("User inactive.")

        APIToken.objects.filter(pk=token.pk).update(last_used_at=timezone.now())
        return (token.user, token)

    def authenticate_header(self, request):
        return self.keyword
