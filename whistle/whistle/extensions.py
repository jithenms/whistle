from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.openapi import AutoSchema

from whistle.auth import ClientAuth, ServerAuth

exclude_paths = [
    "/api/v1/organizations",
    "/api/v1/providers",
]


class CustomOpenApiSettings(AutoSchema):
    def _get_parameters(self):
        parameters = super()._get_parameters()

        if hasattr(self.view, "authentication_classes"):
            for auth_class in self.view.authentication_classes:
                if issubclass(auth_class, ClientAuth):
                    parameters.extend(
                        [
                            {
                                "name": "X-External-Id",
                                "in": "header",
                                "description": "External ID",
                                "required": (
                                    True
                                    if not any(
                                        self.view.request.path.startswith(exclude)
                                        for exclude in exclude_paths
                                    )
                                    else False
                                ),
                                "schema": {
                                    "type": "string",
                                },
                            },
                            {
                                "name": "X-External-Id-Hmac",
                                "in": "header",
                                "description": "External ID HMAC",
                                "required": (
                                    True
                                    if not any(
                                        self.view.request.path.startswith(exclude)
                                        for exclude in exclude_paths
                                    )
                                    else False
                                ),
                                "schema": {
                                    "type": "string",
                                },
                            },
                        ]
                    )
        return parameters


class ClientAuthScheme(OpenApiAuthenticationExtension):
    target_class = ClientAuth
    name = ["bearerAuth", "apiKey"]

    def get_security_definition(self, auto_schema):
        return [
            {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
            {"type": "apiKey", "in": "header", "name": "X-API-Key"},
        ]

    def get_security_requirement(self, auto_schema):
        return [{"bearerAuth": []}, {"apiKey": []}]


class ServerAuthScheme(OpenApiAuthenticationExtension):
    target_class = ServerAuth
    name = ["bearerAuth", "apiKey", "apiSecret"]

    def get_security_definition(self, auto_schema):
        return [
            {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
            {"type": "apiKey", "in": "header", "name": "X-API-Key"},
            {"type": "apiKey", "in": "header", "name": "X-API-Secret"},
        ]

    def get_security_requirement(self, auto_schema):
        return [{"bearerAuth": []}, {"apiKey": [], "apiSecret": []}]


def preprocess_endpoints(endpoints):
    filtered = []
    for path, path_regex, method, callback in endpoints:
        if not any(path.startswith(exclude) for exclude in exclude_paths):
            filtered.append((path, path_regex, method, callback))
    return filtered
