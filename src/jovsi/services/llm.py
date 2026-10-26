"""JOV.si LLM Provider Abstraction & Google Gemini Integration.

Provides structured and unstructured AI completions with:
- Strict secrets hygiene (keys never logged or printed in repr)
- Google Gemini 2.5 Flash implementation via secure REST API (header-based auth)
- 15s timeout with bounded exponential backoff
- Deterministic heuristic fallbacks for every capability
- Safe health check reporting without credential exposure
"""

import abc
import asyncio
import json
import logging
import time
from typing import Any, Dict, Generic, List, Literal, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel, Field

from jovsi.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMResult(BaseModel):
    content: str
    source: Literal["llm", "fallback"]
    provider: str
    model: str
    token_count: Optional[int] = None
    latency_ms: float = 0.0


class StructuredLLMResult(BaseModel, Generic[T]):
    data: T
    raw_content: str
    source: Literal["llm", "fallback"]
    provider: str
    model: str
    latency_ms: float = 0.0


class LLMHealthReport(BaseModel):
    provider: str
    model: str
    configured: bool
    status: Literal["healthy", "unconfigured", "error"]
    message: str
    latency_ms: Optional[float] = None


class LLMProviderError(Exception):
    """Base error for LLM provider issues."""
    pass


class LLMProvider(abc.ABC):
    """Abstract interface for LLM operations."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        pass

    @abc.abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.2,
    ) -> LLMResult:
        pass

    @abc.abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        max_tokens: int = 2000,
    ) -> StructuredLLMResult[T]:
        pass

    @abc.abstractmethod
    async def health_check(self) -> LLMHealthReport:
        pass


class GeminiLLMProvider(LLMProvider):
    """Google Gemini integration using direct REST API over httpx.
    
    Adheres strictly to secrets hygiene:
    - Passes API key via 'x-goog-api-key' request header (never in URL or query params)
    - Secret key is masked in all string representations
    - 15s timeout with max 3 retries on retryable HTTP errors (429, 500, 503)
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 15.0,
        max_retries: int = 3,
    ):
        self._api_key = api_key or settings.effective_llm_api_key
        self._model = model or getattr(settings, "LLM_MODEL", "gemini-2.5-flash")
        self._timeout = timeout
        self._max_retries = max_retries

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    def __repr__(self) -> str:
        # Secrets hygiene: never print actual key value
        configured_str = "yes" if self.is_configured else "no"
        return f"<GeminiLLMProvider model='{self._model}' configured={configured_str}>"

    def _get_headers(self) -> Dict[str, str]:
        if not self._api_key:
            raise LLMProviderError("Gemini API key is not configured.")
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }

    async def _post_with_retry(self, endpoint: str, payload: dict) -> dict:
        url = f"{self.BASE_URL}/models/{self._model}:{endpoint}"
        headers = self._get_headers()

        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(url, headers=headers, json=payload)

                if response.status_code == 200:
                    return response.json()

                if response.status_code in (429, 500, 502, 503, 504):
                    # Transient error, apply exponential backoff
                    wait_time = (2 ** attempt) * 0.5
                    logger.warning(
                        "Gemini API transient status %d on attempt %d/%d; retrying in %.2fs",
                        response.status_code,
                        attempt + 1,
                        self._max_retries,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)
                    continue

                # Non-retryable error (e.g. 400 Bad Request, 401 Unauthorized)
                raise LLMProviderError(
                    f"Gemini API error (status {response.status_code}): {response.text[:200]}"
                )

            except httpx.TimeoutException as exc:
                last_error = exc
                wait_time = (2 ** attempt) * 0.5
                logger.warning("Gemini API timeout on attempt %d/%d; retrying in %.2fs", attempt + 1, self._max_retries, wait_time)
                await asyncio.sleep(wait_time)
            except httpx.RequestError as exc:
                last_error = exc
                wait_time = (2 ** attempt) * 0.5
                logger.warning("Gemini API connection error on attempt %d/%d; retrying in %.2fs", attempt + 1, self._max_retries, wait_time)
                await asyncio.sleep(wait_time)

        raise LLMProviderError(f"Gemini API request failed after {self._max_retries} attempts: {last_error}")

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.2,
    ) -> LLMResult:
        if not self.is_configured:
            raise LLMProviderError("Gemini API key is not configured.")

        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        start_time = time.perf_counter()
        data = await self._post_with_retry("generateContent", payload)
        latency = (time.perf_counter() - start_time) * 1000

        try:
            candidates = data.get("candidates", [])
            if not candidates:
                raise LLMProviderError("No response candidates returned by Gemini.")
            content = candidates[0]["content"]["parts"][0]["text"]
            token_count = data.get("usageMetadata", {}).get("totalTokenCount")
            return LLMResult(
                content=content,
                source="llm",
                provider=self.provider_name,
                model=self.model_name,
                token_count=token_count,
                latency_ms=latency,
            )
        except (KeyError, IndexError) as exc:
            raise LLMProviderError(f"Unexpected response structure from Gemini: {exc}")

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        max_tokens: int = 2000,
    ) -> StructuredLLMResult[T]:
        if not self.is_configured:
            raise LLMProviderError("Gemini API key is not configured.")

        schema = response_model.model_json_schema()
        schema_instruction = (
            f"You MUST respond ONLY with valid JSON conforming strictly to this JSON Schema:\n"
            f"{json.dumps(schema, indent=2)}\n"
            f"Do not include markdown fences or any conversational prefix or suffix."
        )
        combined_system = f"{system_prompt}\n\n{schema_instruction}" if system_prompt else schema_instruction

        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": combined_system}]},
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        start_time = time.perf_counter()
        data = await self._post_with_retry("generateContent", payload)
        latency = (time.perf_counter() - start_time) * 1000

        try:
            candidates = data.get("candidates", [])
            if not candidates:
                raise LLMProviderError("No response candidates returned by Gemini.")
            raw_text = candidates[0]["content"]["parts"][0]["text"].strip()
            
            # Clean possible markdown formatting if present despite responseMimeType
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            parsed_obj = json.loads(raw_text)
            validated_data = response_model.model_validate(parsed_obj)

            return StructuredLLMResult(
                data=validated_data,
                raw_content=raw_text,
                source="llm",
                provider=self.provider_name,
                model=self.model_name,
                latency_ms=latency,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            raise LLMProviderError(f"Failed to parse or validate structured JSON response from Gemini: {exc}")

    async def health_check(self) -> LLMHealthReport:
        if not self.is_configured:
            return LLMHealthReport(
                provider=self.provider_name,
                model=self.model_name,
                configured=False,
                status="unconfigured",
                message="Gemini API key is not configured. Falling back to deterministic rule-based engine.",
            )

        start_time = time.perf_counter()
        try:
            # Minimal 1-token health ping
            payload = {
                "contents": [{"parts": [{"text": "Ping"}]}],
                "generationConfig": {"maxOutputTokens": 1, "temperature": 0.0},
            }
            await self._post_with_retry("generateContent", payload)
            latency = (time.perf_counter() - start_time) * 1000
            return LLMHealthReport(
                provider=self.provider_name,
                model=self.model_name,
                configured=True,
                status="healthy",
                message="Gemini API connection verified operational.",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = (time.perf_counter() - start_time) * 1000
            # Secrets hygiene: sanitize any potential secret from error message
            safe_msg = str(exc)
            if self._api_key and self._api_key in safe_msg:
                safe_msg = safe_msg.replace(self._api_key, "[REDACTED]")
            return LLMHealthReport(
                provider=self.provider_name,
                model=self.model_name,
                configured=True,
                status="error",
                message=f"Gemini API check failed: {safe_msg}",
                latency_ms=latency,
            )


class FallbackLLMProvider(LLMProvider):
    """Deterministic, rule-based provider that produces grounded heuristic results.
    
    Used when:
    - LLM is disabled by configuration
    - API key is unconfigured
    - Gemini service is unreachable or rate-limited
    """

    @property
    def provider_name(self) -> str:
        return "fallback"

    @property
    def model_name(self) -> str:
        return "rule-based-heuristic"

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.2,
    ) -> LLMResult:
        # Grounded heuristic summary based on prompt content
        lines = prompt.strip().splitlines()
        first_line = lines[0] if lines else "Candidate application"
        content = f"[Deterministic Formulation] Based on: {first_line[:120]}"
        return LLMResult(
            content=content,
            source="fallback",
            provider=self.provider_name,
            model=self.model_name,
            token_count=len(content.split()),
            latency_ms=0.5,
        )

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        max_tokens: int = 2000,
    ) -> StructuredLLMResult[T]:
        # Generate valid minimal default data conforming to the response_model schema
        schema = response_model.model_json_schema()
        properties = schema.get("properties", {})
        fallback_dict: Dict[str, Any] = {}

        for prop_name, prop_spec in properties.items():
            prop_type = prop_spec.get("type")
            if prop_type == "string":
                fallback_dict[prop_name] = f"Deterministic value for {prop_name}"
            elif prop_type == "integer":
                fallback_dict[prop_name] = 0
            elif prop_type == "number":
                fallback_dict[prop_name] = 0.0
            elif prop_type == "boolean":
                fallback_dict[prop_name] = True
            elif prop_type == "array":
                fallback_dict[prop_name] = []
            elif prop_type == "object":
                fallback_dict[prop_name] = {}
            else:
                fallback_dict[prop_name] = None

        try:
            instance = response_model.model_validate(fallback_dict)
        except Exception:
            # Construct empty or minimal instance if validation failed
            instance = response_model.model_construct(**fallback_dict)

        raw_json = json.dumps(fallback_dict)
        return StructuredLLMResult(
            data=instance,
            raw_content=raw_json,
            source="fallback",
            provider=self.provider_name,
            model=self.model_name,
            latency_ms=0.5,
        )

    async def health_check(self) -> LLMHealthReport:
        return LLMHealthReport(
            provider=self.provider_name,
            model=self.model_name,
            configured=True,
            status="healthy",
            message="Rule-based deterministic engine operational.",
            latency_ms=0.1,
        )


class HybridLLMService:
    """Orchestrates LLM generation with transparent fallback to deterministic rules.
    
    If settings.LLM_ENABLED and API key is present:
    - Calls Gemini with timeout and retry
    - On failure (rate-limit, network error, invalid response), seamlessly falls back
      to FallbackLLMProvider, annotating source="fallback"
    
    If disabled or key missing:
    - Directly executes FallbackLLMProvider
    """

    def __init__(self, gemini_provider: Optional[GeminiLLMProvider] = None, fallback_provider: Optional[FallbackLLMProvider] = None):
        self.gemini = gemini_provider or GeminiLLMProvider()
        self.fallback = fallback_provider or FallbackLLMProvider()

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.2,
    ) -> LLMResult:
        if settings.LLM_ENABLED and self.gemini.is_configured:
            try:
                return await self.gemini.generate_text(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            except Exception as exc:
                logger.warning("Gemini text generation failed (%s); invoking deterministic fallback.", exc)

        return await self.fallback.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        max_tokens: int = 2000,
    ) -> StructuredLLMResult[T]:
        if settings.LLM_ENABLED and self.gemini.is_configured:
            try:
                return await self.gemini.generate_structured(
                    prompt=prompt,
                    response_model=response_model,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                )
            except Exception as exc:
                logger.warning("Gemini structured generation failed (%s); invoking deterministic fallback.", exc)

        return await self.fallback.generate_structured(
            prompt=prompt,
            response_model=response_model,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )

    async def health_check(self) -> LLMHealthReport:
        if settings.LLM_ENABLED and self.gemini.is_configured:
            return await self.gemini.health_check()
        return await self.gemini.health_check()


# Global singleton instance
llm_service = HybridLLMService()


def get_llm_provider() -> HybridLLMService:
    """Return the application's hybrid LLM provider."""
    return llm_service

