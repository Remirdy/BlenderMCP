"""AI 3D-generation provider layer.

A small, honest abstraction over hosted and local image-to-3D backends. Every
provider reports whether it is configured and what is missing, so the MCP client
gets a clear setup error instead of a silent failure. The registry can run a
single named provider or an ``auto`` fallback chain across several.
"""
from __future__ import annotations

from .base import (
    ProviderError,
    ProviderNotConfigured,
    ProviderResult,
    ImageTo3DProvider,
)
from .registry import (
    PROVIDERS,
    get_provider,
    list_provider_status,
    generate_from_image,
)

__all__ = [
    "ProviderError",
    "ProviderNotConfigured",
    "ProviderResult",
    "ImageTo3DProvider",
    "PROVIDERS",
    "get_provider",
    "list_provider_status",
    "generate_from_image",
]
