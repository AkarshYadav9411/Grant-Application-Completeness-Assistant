"""
Consistent error response format used across the API.

All errors follow: {"error": {"code": "ERROR_CODE", "message": "Human-readable message."}}
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Build a consistent JSON error response."""
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error=ErrorDetail(code=code, message=message)
        ).model_dump(),
    )


def raise_error(status_code: int, code: str, message: str) -> None:
    """Raise an HTTPException with the standard error format."""
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTPExceptions and return consistent error format."""
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        return error_response(exc.status_code, detail["code"], detail["message"])
    return error_response(
        exc.status_code,
        f"HTTP_{exc.status_code}",
        str(detail) if detail else "An error occurred.",
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions and return a generic error."""
    return error_response(
        500,
        "INTERNAL_SERVER_ERROR",
        "An unexpected error occurred. Please try again later.",
    )


async def starlette_http_exception_handler(request: Request, exc) -> JSONResponse:
    """Handle Starlette's base HTTPException (e.g. 404 for unmatched routes)."""
    detail = getattr(exc, "detail", None)
    status_code = getattr(exc, "status_code", 500)
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        return error_response(status_code, detail["code"], detail["message"])
    return error_response(
        status_code,
        f"HTTP_{status_code}",
        str(detail) if detail else "An error occurred.",
    )
