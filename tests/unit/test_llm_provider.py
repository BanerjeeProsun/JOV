"""Unit tests for LLM provider abstraction, Google Gemini client, and deterministic fallback."""

import json
from typing import List, Optional
import pytest
from pydantic import BaseModel
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from fastapi.testclient import TestClient

from jovsi.api.main import app
from jovsi.services.llm import (
    GeminiLLMProvider,
    FallbackLLMProvider,
    HybridLLMService,
    LLMProviderError,
    LLMResult,
    StructuredLLMResult,
)


class SampleJobRequirements(BaseModel):
    role_title: str
    minimum_years: int
    required_skills: List[str]
    is_remote: bool


@pytest.mark.asyncio
async def test_gemini_repr_does_not_leak_key():
    """Verify that Gemini provider string representation never prints the API key."""
    secret = "AIzaSySecretKeyNeverPrintThis12345"
    provider = GeminiLLMProvider(api_key=secret, model="gemini-2.5-flash")
    repr_str = repr(provider)
    str_str = str(provider)

    assert secret not in repr_str
    assert secret not in str_str
    assert "configured=yes" in repr_str


@pytest.mark.asyncio
async def test_gemini_unconfigured_behavior():
    """Verify that Gemini provider handles missing configuration gracefully."""
    provider = GeminiLLMProvider(api_key="", model="gemini-2.5-flash")
    assert not provider.is_configured

    report = await provider.health_check()
    assert not report.configured
    assert report.status == "unconfigured"
    assert "not configured" in report.message.lower()

    with pytest.raises(LLMProviderError) as exc_info:
        await provider.generate_text("Hello")
    assert "not configured" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_fallback_provider_text_and_structured():
    """Verify fallback provider returns valid heuristic responses and schema conformance."""
    fallback = FallbackLLMProvider()
    assert fallback.provider_name == "fallback"

    # Text completion
    text_result = await fallback.generate_text("Draft a bullet point for Python API development")
    assert isinstance(text_result, LLMResult)
    assert text_result.source == "fallback"
    assert text_result.provider == "fallback"
    assert len(text_result.content) > 0

    # Structured completion
    struct_result = await fallback.generate_structured(
        prompt="Parse Senior Backend Engineer requirements",
        response_model=SampleJobRequirements,
    )
    assert isinstance(struct_result, StructuredLLMResult)
    assert struct_result.source == "fallback"
    assert isinstance(struct_result.data, SampleJobRequirements)
    assert isinstance(struct_result.data.required_skills, list)

    # Health check
    health = await fallback.health_check()
    assert health.status == "healthy"
    assert health.configured


@pytest.mark.asyncio
async def test_gemini_mocked_successful_text_and_structured():
    """Verify Gemini provider parses real Gemini REST API responses."""
    fake_key = "AIzaSyTestKeyForMockOnly123456789012"
    provider = GeminiLLMProvider(api_key=fake_key, model="gemini-2.5-flash")

    # Mock text response
    mock_text_response = MagicMock(spec=httpx.Response)
    mock_text_response.status_code = 200
    mock_text_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Engineered high-throughput FastAPI distributed pipeline."}],
                    "role": "model",
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {"totalTokenCount": 42},
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_text_response
        result = await provider.generate_text("Write bullet")
        assert result.source == "llm"
        assert result.provider == "gemini"
        assert "high-throughput" in result.content
        assert result.token_count == 42

        # Verify key was passed in header, not URL
        args, kwargs = mock_post.call_args
        assert "key=" not in args[0]
        assert kwargs["headers"]["x-goog-api-key"] == fake_key

    # Mock structured JSON response
    mock_struct_response = MagicMock(spec=httpx.Response)
    mock_struct_response.status_code = 200
    mock_struct_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "role_title": "Principal Architect",
                                    "minimum_years": 8,
                                    "required_skills": ["Python", "FastAPI", "PostgreSQL"],
                                    "is_remote": True,
                                }
                            )
                        }
                    ],
                    "role": "model",
                },
                "finishReason": "STOP",
            }
        ],
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_struct_response
        struct_res = await provider.generate_structured("Extract requirements", SampleJobRequirements)
        assert struct_res.source == "llm"
        assert struct_res.data.role_title == "Principal Architect"
        assert struct_res.data.minimum_years == 8
        assert "FastAPI" in struct_res.data.required_skills
        assert struct_res.data.is_remote is True


@pytest.mark.asyncio
async def test_hybrid_service_falls_back_on_gemini_error():
    """Verify that HybridLLMService transparently invokes fallback if Gemini fails."""
    fake_key = "AIzaSyTestKeyForMockOnly123456789012"
    gemini = GeminiLLMProvider(api_key=fake_key, max_retries=1)
    fallback = FallbackLLMProvider()
    hybrid = HybridLLMService(gemini_provider=gemini, fallback_provider=fallback)

    with patch("jovsi.config.settings.LLM_ENABLED", True):
        # Force an error in Gemini
        with patch.object(gemini, "_post_with_retry", side_effect=LLMProviderError("Quota exceeded")):
            result = await hybrid.generate_text("Prompt needing completion")
            assert result.source == "fallback"
            assert result.provider == "fallback"

            struct_res = await hybrid.generate_structured("Prompt", SampleJobRequirements)
            assert struct_res.source == "fallback"
            assert isinstance(struct_res.data, SampleJobRequirements)


def test_health_llm_api_endpoint():
    """Verify the /api/v1/health/llm endpoint returns expected report without exposing secrets."""
    client = TestClient(app)
    response = client.get("/api/v1/health/llm")
    assert response.status_code == 200
    data = response.json()
    assert "provider" in data
    assert "model" in data
    assert "configured" in data
    assert "status" in data
    assert "message" in data
    assert data["status"] in ("healthy", "unconfigured", "error")
