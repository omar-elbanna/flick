"""Async OpenAI Chat Completions client with strict JSON parsing."""

from __future__ import annotations

import contextlib
import json
from typing import Any

import httpx
import structlog
from fastapi import HTTPException, status
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings

log = structlog.get_logger(__name__)

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_TIMEOUT = httpx.Timeout(30.0, connect=5.0)


class OpenAIError(HTTPException):
    def __init__(self, message: str = "AI recommendation request failed.") -> None:
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"detail": message, "code": "OPENAI_ERROR"},
        )


async def _call(messages: list[dict[str, str]], json_response: bool) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": settings.OPENAI_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2200,
    }
    if json_response:
        body["response_format"] = {"type": "json_object"}

    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT) as client:
                    resp = await client.post(
                        OPENAI_URL,
                        headers={
                            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json=body,
                    )
                if resp.status_code in (500, 502, 503, 504):
                    resp.raise_for_status()
                if resp.status_code >= 400:
                    err_body: dict[str, Any] = {}
                    with contextlib.suppress(Exception):
                        err_body = resp.json().get("error", {}) or {}
                    err_code = str(err_body.get("code") or "")
                    err_message = str(err_body.get("message") or "")
                    log.warning(
                        "openai.client_error",
                        status_code=resp.status_code,
                        error_code=err_code,
                    )
                    if err_code == "insufficient_quota" or "quota" in err_message.lower():
                        raise OpenAIError(
                            "OpenAI account has no remaining credit. Add billing at "
                            "platform.openai.com/settings/organization/billing."
                        )
                    if err_code == "invalid_api_key" or resp.status_code == 401:
                        raise OpenAIError("OpenAI API key is invalid or revoked.")
                    if resp.status_code == 429:
                        raise OpenAIError("OpenAI rate limit hit. Try again in a moment.")
                    raise OpenAIError(
                        f"OpenAI error: {err_message or f'HTTP {resp.status_code}'}."
                    )
                return resp.json()
    except RetryError as exc:
        log.error("openai.retry_exhausted")
        raise OpenAIError("AI service unavailable.") from exc
    except httpx.HTTPError as exc:
        log.error("openai.request_error", error_type=type(exc).__name__)
        raise OpenAIError("AI request failed.") from exc
    raise OpenAIError("Unknown AI error.")


async def call_with_retry(
    messages: list[dict[str, str]], *, json_response: bool = True
) -> dict[str, Any]:
    """Call the chat completion endpoint and parse the assistant message.

    If json_response is True, parses the message content as JSON. On a single
    parse failure we retry the request once with an explicit reminder.
    """

    raw = await _call(messages, json_response=json_response)
    try:
        content = raw["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        log.error("openai.malformed_response_envelope")
        raise OpenAIError("AI response missing expected fields.") from exc

    if not json_response:
        return {"content": content}

    try:
        return _parse_json(content)
    except ValueError:
        log.info("openai.json_parse_retry")
        retry_messages = messages + [
            {"role": "assistant", "content": content},
            {
                "role": "user",
                "content": (
                    "Your previous reply was not valid JSON. Reply again with only the "
                    "JSON object — no prose, no markdown fences."
                ),
            },
        ]
        retry = await _call(retry_messages, json_response=True)
        try:
            retry_content = retry["choices"][0]["message"]["content"]
            return _parse_json(retry_content)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise OpenAIError("AI returned malformed JSON twice.") from exc


def _parse_json(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].lstrip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError("not JSON") from exc
