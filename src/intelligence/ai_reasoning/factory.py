"""Phase 22 — AI Reasoning Provider Factory.

Enables seamless switching between providers (Gemini, Claude, Mock) via configuration / environment variables.
"""
from __future__ import annotations

import os
from typing import Optional
from src.intelligence.ai_reasoning.gemini_provider import GeminiAIProvider
from src.intelligence.ai_reasoning.mock_provider import MockAIProvider
from src.intelligence.ai_reasoning.provider_interface import AIReasoningProvider


def get_ai_reasoning_provider(provider_type: Optional[str] = None) -> AIReasoningProvider:
    """Instantiate and return the configured AI Reasoning Provider.

    Provider resolution order:
    1. Explicit provider_type parameter
    2. AI_PROVIDER environment variable
    3. Default to 'gemini' if GEMINI_API_KEY is set, else 'mock'
    """
    prov = (provider_type or os.environ.get("AI_PROVIDER", "")).strip().lower()

    if prov == "gemini":
        return GeminiAIProvider()
    elif prov == "mock":
        return MockAIProvider()
    elif prov == "claude":
        # Placeholder for Claude Opus / Sonnet once API key is renewed
        raise NotImplementedError("Claude provider is configured but currently awaiting API key renewal. Use AI_PROVIDER=gemini.")
    else:
        # Auto-detect: if GEMINI_API_KEY is available, use gemini, else mock
        if os.environ.get("GEMINI_API_KEY"):
            return GeminiAIProvider()
        return MockAIProvider()
