"""Provider interfaces and shared result types."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


class ProviderError(RuntimeError):
    """A provider attempted work and failed (network, API error, timeout)."""


class ProviderNotConfigured(ProviderError):
    """A provider cannot run because required configuration is missing.

    This is distinct from ProviderError so the registry can skip an
    unconfigured provider in an ``auto`` chain without treating it as a hard
    failure, and so tools can return actionable setup hints.
    """


@dataclass
class ProviderResult:
    provider: str
    glb_path: str
    task_id: str | None = None
    thumbnail_url: str | None = None
    runtime_seconds: float | None = None
    cost_note: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GenerationOptions:
    """Normalized options passed to every provider.

    Providers translate these into their own request schema. Unknown extras are
    kept in ``extra`` so power users can pass provider-specific knobs without a
    code change.
    """

    target_polycount: int = 100000
    enable_pbr: bool = True
    should_texture: bool = True
    topology: str = "quad"          # quad | triangle
    pose_mode: str = "a-pose"       # a-pose | t-pose | original
    symmetry: str = "auto"          # auto | on | off
    quality: str = "high"           # draft | regular | high | ultra
    seed: int | None = None
    # Multi-view: extra reference images (side/back) when the sprite sheet
    # yields more than one usable pose. Providers that support multi-image
    # conditioning use these; single-image providers ignore them.
    extra_views: list[str] = field(default_factory=list)
    wait_seconds: int = 1200
    poll_interval: int = 8
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_params(cls, params: dict[str, Any] | None) -> "GenerationOptions":
        params = dict(params or {})
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        kwargs = {k: v for k, v in params.items() if k in known and v is not None}
        extra = {k: v for k, v in params.items() if k not in known}
        opts = cls(**kwargs)
        opts.extra.update(extra)
        return opts


class ImageTo3DProvider(ABC):
    """Base class for image-to-3D backends.

    Subclasses implement ``_required_env`` and ``generate``. The registry only
    ever calls ``is_configured`` / ``missing_config`` / ``generate``.
    """

    name: str = "base"
    kind: str = "hosted"            # hosted | local
    supports_multiview: bool = False
    homepage: str = ""

    # --- configuration -------------------------------------------------
    def _required_env(self) -> list[str]:
        """Env var names; ANY one present counts as configured (OR semantics)."""
        return []

    def is_configured(self) -> bool:
        required = self._required_env()
        if not required:
            return True
        return any(os.environ.get(name) for name in required)

    def missing_config(self) -> list[str]:
        if self.is_configured():
            return []
        return self._required_env()

    def status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "configured": self.is_configured(),
            "supports_multiview": self.supports_multiview,
            "missing_env": self.missing_config(),
            "homepage": self.homepage,
        }

    # --- helpers -------------------------------------------------------
    def _api_key(self) -> str:
        for name in self._required_env():
            value = os.environ.get(name)
            if value:
                return value
        raise ProviderNotConfigured(
            f"{self.name}: set one of {', '.join(self._required_env())}"
        )

    @staticmethod
    def _ensure_parent(glb_path: str) -> str:
        path = Path(glb_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    # --- work ----------------------------------------------------------
    @abstractmethod
    def generate(self, image_path: str, glb_path: str, opts: GenerationOptions) -> ProviderResult:
        """Produce a textured GLB at ``glb_path`` from ``image_path``."""
        raise NotImplementedError
