"""A small provider boundary. API keys never enter prompts or benchmark reports."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import ipaddress
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse

from .models import ReasoningError, strict_json


class ProviderError(ReasoningError):
    pass


@dataclass(frozen=True)
class ProviderReply:
    text: str
    usage: dict[str, int] = field(default_factory=dict)


class ReasoningProvider(Protocol):
    name: str
    model: str

    def generate(self, system: str, user: str, schema: dict[str, Any]) -> ProviderReply:
        ...


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-6.1-sol", *,
                 effort: str = "medium", timeout: float = 45,
                 max_output_tokens: int = 4096,
                 transport: Callable[..., Any] | None = None):
        if not isinstance(api_key, str) or not api_key.strip():
            raise ProviderError("An OpenAI API key is required. Enter it locally at the hidden prompt.")
        if any(char in api_key for char in ("\r", "\n")):
            raise ProviderError("The API key contains invalid characters.")
        if not model or len(model) > 100:
            raise ProviderError("A valid model name is required.")
        if effort not in ("low", "medium", "high"):
            raise ProviderError("Reasoning effort must be low, medium, or high.")
        if not 1 <= timeout <= 300 or not 512 <= max_output_tokens <= 16384:
            raise ProviderError("Invalid request timeout or output-token limit.")
        self.model, self.effort = model, effort
        self.timeout, self.max_output_tokens = timeout, max_output_tokens
        self._api_key = api_key.strip()
        self._transport = transport or urlopen

    def generate(self, system: str, user: str, schema: dict[str, Any]) -> ProviderReply:
        payload = {
            "model": self.model,
            "input": [{"role": "developer", "content": system},
                      {"role": "user", "content": user}],
            "reasoning": {"effort": self.effort},
            "text": {"format": {"type": "json_schema", "name": "zaenia_decision",
                                "strict": True, "schema": schema}},
            "store": False,
            "max_output_tokens": self.max_output_tokens,
        }
        request = Request("https://api.openai.com/v1/responses",
                          data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"),
                          headers={"Authorization": "Bearer " + self._api_key,
                                   "Content-Type": "application/json"}, method="POST")
        try:
            with self._transport(request, timeout=self.timeout) as response:
                body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise ProviderError("The API response exceeded the size limit.")
            data = strict_json(body.decode("utf-8"))
        except HTTPError as error:
            explanations = {
                400: "The model or request settings were rejected. Check model access and structured-output support.",
                401: "The API key was rejected.",
                403: "This API project does not have access to the requested model.",
                404: "The requested model is unavailable to this API project.",
                429: "The API reported a rate limit or billing/quota limit.",
            }
            raise ProviderError(explanations.get(error.code, "OpenAI returned HTTP " + str(error.code) + ".")) from None
        except (URLError, TimeoutError, OSError):
            raise ProviderError("OpenAI could not be reached before the timeout. No local fallback was substituted.") from None
        except (ValueError, UnicodeError, RecursionError):
            raise ProviderError("OpenAI returned an unreadable response.") from None
        return self._read_response(data)

    @staticmethod
    def _read_response(data: Any) -> ProviderReply:
        if not isinstance(data, dict) or data.get("status") != "completed":
            raise ProviderError("OpenAI did not complete the response. No partial decision was accepted.")
        pieces: list[str] = []
        output = data.get("output")
        if not isinstance(output, list):
            raise ProviderError("OpenAI returned no decision.")
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue  # Raw reasoning is deliberately not read or recorded.
            content = item.get("content", [])
            if not isinstance(content, list):
                raise ProviderError("OpenAI returned an invalid message.")
            for part in content:
                if not isinstance(part, dict):
                    raise ProviderError("OpenAI returned an invalid message.")
                if part.get("type") == "refusal":
                    raise ProviderError("The OpenAI model declined this request.")
                if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    pieces.append(part["text"])
        if not pieces:
            raise ProviderError("OpenAI returned no decision text.")
        usage = data.get("usage", {})
        safe_usage: dict[str, int] = {}
        if isinstance(usage, dict):
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                value = usage.get(key)
                if type(value) is int and value >= 0:
                    safe_usage[key] = value
            details = usage.get("output_tokens_details", {})
            if isinstance(details, dict) and type(details.get("reasoning_tokens")) is int:
                safe_usage["reasoning_tokens"] = max(0, details["reasoning_tokens"])
        return ProviderReply("".join(pieces), safe_usage)


class ExistingLocalProvider:
    """Use the reviewed chat_local interface, including its existing local settings."""
    name = "local"

    def __init__(self, *, timeout: int = 120, chat: Callable[..., str] | None = None,
                 model: str = "configured-local-model"):
        if chat is None:
            try:
                from core.brain.local_llm import chat_local, get_brain_settings
                settings = get_brain_settings()
                endpoint = urlparse(str(settings["endpoint"]))
                host = endpoint.hostname or ""
                try:
                    loopback = ipaddress.ip_address(host).is_loopback
                except ValueError:
                    loopback = host.casefold() == "localhost"
                if endpoint.scheme not in ("http", "https") or not loopback or endpoint.username or endpoint.password:
                    raise ValueError("Local provider requires a loopback endpoint without embedded credentials.")
                self.model = str(settings["model"])
                self._chat = chat_local
            except Exception:
                raise ProviderError("The existing local brain could not be loaded. Check its configuration and dependencies.") from None
        else:
            self.model, self._chat = model, chat
        self.timeout = timeout

    def generate(self, system: str, user: str, schema: dict[str, Any]) -> ProviderReply:
        prompt = ("TASK INSTRUCTIONS\n" + system + "\n\nOUTPUT JSON SCHEMA\n"
                  + json.dumps(schema, ensure_ascii=False)
                  + "\n\nREQUEST AND REFERENCE DATA\n" + user
                  + "\n\nReturn only a JSON object matching the schema. No Markdown fences.")
        try:
            answer = self._chat(prompt, timeout=self.timeout)
        except Exception:
            raise ProviderError("The existing local brain failed to answer. Check that Ollama and its configured model are available.") from None
        if not isinstance(answer, str) or not answer.strip():
            raise ProviderError("The local brain returned no decision text.")
        return ProviderReply(answer)
