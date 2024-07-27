from drf_spectacular.authentication import OpenApiAuthenticationExtension


class ClientAuthScheme(OpenApiAuthenticationExtension):
    target_class = "whistle.auth.ClientAuth"
    name = ["bearerAuth", "apiKey"]

    def get_security_definition(self, auto_schema):
        return [
            {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
            {"type": "apiKey", "in": "header", "name": "X-API-Key"},
        ]

    def get_security_requirement(self, auto_schema):
        return [{"bearerAuth": []}, {"apiKey": []}]


class ServerAuthScheme(OpenApiAuthenticationExtension):
    target_class = "whistle.auth.ServerAuth"
    name = ["bearerAuth", "apiKey", "apiSecret"]

    def get_security_definition(self, auto_schema):
        return [
            {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
            {"type": "apiKey", "in": "header", "name": "X-API-Key"},
            {"type": "apiKey", "in": "header", "name": "X-API-Secret"},
        ]

    def get_security_requirement(self, auto_schema):
        return [{"bearerAuth": []}, {"apiKey": [], "apiSecret": []}]
