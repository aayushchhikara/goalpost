"""One error shape everywhere: a machine code, a readable message and optional field details."""

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from goalpost.schemas.errors import ErrorDetail, ErrorResponse


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, field: str | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.field = field

    def to_response(self) -> ErrorResponse:
        details = [ErrorDetail(field=self.field, message=self.message)] if self.field else []
        return ErrorResponse(code=self.code, message=self.message, details=details)


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class Invalid(AppError):
    status_code = 422
    code = "validation_error"


def _json(status_code: int, body: ErrorResponse) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


async def _app_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return _json(exc.status_code, exc.to_response())


async def _validation_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = [
        # Drop the leading "body" / "query" / "path" from the location.
        ErrorDetail(
            field=".".join(str(part) for part in err["loc"][1:]) or None, message=err["msg"]
        )
        for err in exc.errors()
    ]
    body = ErrorResponse(code="validation_error", message="Request is invalid", details=details)
    return _json(422, body)


async def _http_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = HTTPStatus(exc.status_code).phrase.lower().replace(" ", "_")
    return _json(exc.status_code, ErrorResponse(code=code, message=str(exc.detail), details=[]))


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
