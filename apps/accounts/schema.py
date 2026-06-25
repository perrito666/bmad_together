"""drf-spectacular extension so the personal-access-token auth shows up in the schema."""
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class PersonalAccessTokenScheme(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.authentication.PersonalAccessTokenAuthentication"
    name = "PersonalAccessToken"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "Personal access token, sent as `Token <prefix>.<secret>`.",
        }
