"""One error shape for the whole API: {"error": {"code", "message", "details"}}."""

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from ninja import NinjaAPI
from ninja.errors import AuthenticationError, ValidationError


class ServiceError(Exception):
    """Raise from services/ for expected business-rule failures."""

    def __init__(self, code: str, message: str, status: int = 400, details=None):
        super().__init__(message)
        self.code, self.message, self.status, self.details = code, message, status, details


def _body(code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def register_error_handlers(api: NinjaAPI) -> None:
    @api.exception_handler(ServiceError)
    def service_error(request, exc: ServiceError):
        return api.create_response(request, _body(exc.code, exc.message, exc.details), status=exc.status)

    @api.exception_handler(ObjectDoesNotExist)
    def not_found(request, exc):
        return api.create_response(request, _body("not_found", "Not found."), status=404)

    @api.exception_handler(PermissionDenied)
    def forbidden(request, exc):
        return api.create_response(request, _body("forbidden", "You do not have access."), status=403)

    @api.exception_handler(AuthenticationError)
    def unauthenticated(request, exc):
        return api.create_response(request, _body("unauthenticated", "Sign in required."), status=401)

    @api.exception_handler(ValidationError)
    def invalid(request, exc: ValidationError):
        return api.create_response(request, _body("invalid", "Invalid input.", exc.errors), status=422)
