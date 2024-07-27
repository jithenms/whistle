from rest_framework.pagination import LimitOffsetPagination


class StandardLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 50
    min_limit = 1

    min_offset = 0
    default_offset = 0

    def get_schema_operation_parameters(self, view):
        return [
            {
                "name": self.limit_query_param,
                "required": False,
                "in": "query",
                "description": "Number of results to return per page.",
                "schema": {
                    "type": "integer",
                    "default": self.default_limit,
                    "maximum": self.max_limit,
                    "minimum": self.min_limit,
                },
            },
            {
                "name": self.offset_query_param,
                "required": False,
                "in": "query",
                "description": "The initial index from which to return the results.",
                "schema": {
                    "type": "integer",
                    "minimum": self.min_offset,
                    "default": self.default_offset,
                },
            },
        ]
