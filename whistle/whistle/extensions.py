from drf_spectacular.authentication import OpenApiAuthenticationExtension

from whistle.auth import ClientAuth, ServerAuth


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
    included = ["users", "notifications", "broadcasts", "audiences", "devices", "preferences", "subscriptions"]
    for (path, path_regex, method, callback) in endpoints:
        if any(include in path for include in included):
            filtered.append((path, path_regex, method, callback))
    return filtered
