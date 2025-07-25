import logging

from django.db import IntegrityError
from django.http import JsonResponse, Http404
from rest_framework import status
from rest_framework.exceptions import (
    ValidationError,
    AuthenticationFailed,
    PermissionDenied,
    MethodNotAllowed,
    ParseError,
)
from rest_framework.utils.serializer_helpers import ReturnDict
from rest_framework.views import exception_handler


class NotificationException(Exception):
    def __init__(self, message, code):
        self.message = message
        self.code = code


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        if isinstance(exc, AuthenticationFailed):
            response.data["code"] = exc.get_codes()
            response.data["detail"] = exc.detail
            response.data["type"] = "authentication_error"
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return response
        elif isinstance(exc, ValidationError):
            if isinstance(exc.get_codes(), str):
                code = exc.get_codes()
            else:
                code = "invalid_payload"

            if isinstance(exc.detail, ReturnDict):
                for key in exc.detail:
                    if isinstance(exc.detail[key], list) and len(exc.detail[key]) == 1:
                        exc.detail[key] = exc.detail[key][0]
                detail = exc.detail
            elif isinstance(exc.detail, list):
                if len(exc.detail) == 1:
                    detail = exc.detail[0]
                else:
                    detail = exc.detail
            else:
                detail = exc.detail

            if isinstance(exc.detail, str):
                detail = exc.detail

            if isinstance(exc.detail, dict):
                for field, errors in detail.items():
                    if isinstance(errors, dict) and "non_field_errors" in errors:
                        if (
                            isinstance(errors["non_field_errors"], list)
                            and len(errors["non_field_errors"]) == 1
                        ):
                            detail[field] = errors["non_field_errors"][0]
                        else:
                            detail[field] = errors["non_field_errors"]
                    else:
                        detail[field] = errors

            return generate_error_response(code=code, detail=detail)
        elif isinstance(exc, PermissionDenied):
            response.data["type"] = "permission_error"
            response.data["code"] = exc.get_codes()
            response.data["detail"] = exc.detail
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return response
        elif isinstance(exc, Http404):
            response.data["type"] = "not_found"
            response.data["detail"] = "Resource not found"
            response.status_code = status.HTTP_404_NOT_FOUND
            return response
        elif isinstance(exc, MethodNotAllowed):
            response.data["type"] = "not_allowed"
            response.data["detail"] = "Method not allowed"
            response.status_code = status.HTTP_403_FORBIDDEN
            return response
        elif isinstance(exc, ParseError):
            response.data["type"] = "validation_error"
            response.data["code"] = "invalid_payload"
            response.data["detail"] = "Malformed request data"
            return response

    if isinstance(exc, IntegrityError):
        if "unique constraint" in str(exc):
            return generate_error_response(
                "data_integrity_error",
                "unique_constraint_error",
                status.HTTP_400_BAD_REQUEST,
                "The record you are trying to create violates a unique constraint. Please ensure your request does not "
                "contain existing identifiers or slugs.",
            )

    logging.info("Unrecognized exception: %s", exc)

    return generate_error_response(
        "server_error",
        "internal_error",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "An unexpected error occurred. Please try again later.",
    )


def generate_error_response(
    type="validation_error",
    code="invalid",
    status_code=status.HTTP_400_BAD_REQUEST,
    detail=None,
):
    return JsonResponse(
        {"type": type, "code": code, "detail": detail}, status=status_code
    )
