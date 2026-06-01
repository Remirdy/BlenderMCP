"""Registry and orchestration layer for 3D generation providers.

Supports running a single provider, an auto fallback chain, or parallel execution
of Cloud and Local pipelines.
"""
from __future__ import annotations

import concurrent.futures
import logging
import time
from typing import Any

from .base import (
    GenerationOptions,
    ImageTo3DProvider,
    ProviderError,
    ProviderNotConfigured,
    ProviderResult,
)
from .image_to_3d import (
    Hunyuan3DProvider,
    LocalCommandProvider,
    MeshyProvider,
    RodinProvider,
    TripoProvider,
)

log = logging.getLogger("remirdy.providers")

# Instantiate all available providers
_PROVIDERS_LIST: list[ImageTo3DProvider] = [
    MeshyProvider(),
    TripoProvider(),
    RodinProvider(),
    Hunyuan3DProvider(),
    LocalCommandProvider(),
]

PROVIDERS: dict[str, ImageTo3DProvider] = {p.name: p for p in _PROVIDERS_LIST}


def get_provider(name: str) -> ImageTo3DProvider:
    """Look up a provider by name."""
    provider = PROVIDERS.get(name.lower().strip())
    if not provider:
        raise ValueError(f"Unknown provider '{name}'. Available: {', '.join(PROVIDERS.keys())}")
    return provider


def list_provider_status() -> list[dict[str, Any]]:
    """Return status reports for all providers in the registry."""
    return [p.status() for p in _PROVIDERS_LIST]


def _run_single_provider(
    provider: ImageTo3DProvider, image_path: str, glb_path: str, opts: GenerationOptions
) -> ProviderResult:
    """Safely execute a single provider's generate method."""
    if not provider.is_configured():
        raise ProviderNotConfigured(
            f"Provider '{provider.name}' is missing configuration: {', '.join(provider.missing_config())}"
        )
    log.info("Executing generation with provider: %s", provider.name)
    return provider.generate(image_path, glb_path, opts)


def generate_from_image(
    image_path: str, glb_path: str, opts: GenerationOptions, provider_name: str = "auto"
) -> ProviderResult:
    """Generate a 3D model from a 2D image.

    Supports:
    - Specific provider name (e.g. 'meshy', 'local_command')
    - 'parallel': runs Cloud and Local pipelines concurrently, returning the fastest winner.
    - 'auto': tries configured cloud/local providers in sequence.
    """
    provider_name = provider_name.lower().strip()

    if provider_name == "parallel":
        return generate_parallel(image_path, glb_path, opts)

    if provider_name == "auto":
        # First check cloud, then local in sequence
        errors = []
        candidates = ["meshy", "tripo", "rodin", "hunyuan3d", "local_command"]
        for name in candidates:
            p = PROVIDERS.get(name)
            if p and p.is_configured():
                try:
                    return _run_single_provider(p, image_path, glb_path, opts)
                except ProviderError as exc:
                    log.warning("Auto fallback provider '%s' failed: %s", name, exc)
                    errors.append(f"{name}: {exc}")
        raise ProviderError(
            f"All auto fallback providers failed or were not configured: {'; '.join(errors)}"
        )

    # Specific named provider
    p = get_provider(provider_name)
    return _run_single_provider(p, image_path, glb_path, opts)


def generate_parallel(
    image_path: str, glb_path: str, opts: GenerationOptions
) -> ProviderResult:
    """Execute a Cloud pipeline and a Local/Offline pipeline concurrently in parallel.

    Whichever pipeline yields a successful model first is returned.
    If one fails or is not configured, we wait for the other.
    If both fail, raises ProviderError.
    """
    log.info("Starting dual parallel pipelines: Cloud vs Local/Offline")

    # Select the best configured cloud provider
    cloud_provider: ImageTo3DProvider | None = None
    for name in ["meshy", "tripo", "rodin"]:
        p = PROVIDERS.get(name)
        if p and p.is_configured():
            cloud_provider = p
            break

    # Select the best configured local provider
    local_provider: ImageTo3DProvider | None = None
    for name in ["hunyuan3d", "local_command"]:
        p = PROVIDERS.get(name)
        if p and p.is_configured():
            local_provider = p
            break

    if not cloud_provider and not local_provider:
        raise ProviderNotConfigured(
            "Parallel pipeline error: Neither a cloud provider nor a local command provider is configured."
        )

    # Target path variants to prevent file collision in parallel threads
    import os
    from pathlib import Path

    base_glb = Path(glb_path)
    cloud_glb = str(base_glb.with_name(f"{base_glb.stem}_cloud{base_glb.suffix}"))
    local_glb = str(base_glb.with_name(f"{base_glb.stem}_local{base_glb.suffix}"))

    futures_map = {}
    started = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        if cloud_provider:
            log.info("Launching Cloud Pipeline (%s) in parallel thread", cloud_provider.name)
            f_cloud = executor.submit(
                _run_single_provider, cloud_provider, image_path, cloud_glb, opts
            )
            futures_map[f_cloud] = ("cloud", cloud_provider.name, cloud_glb)

        if local_provider:
            log.info("Launching Local Pipeline (%s) in parallel thread", local_provider.name)
            f_local = executor.submit(
                _run_single_provider, local_provider, image_path, local_glb, opts
            )
            futures_map[f_local] = ("local", local_provider.name, local_glb)

        errors = []
        done_futures = []

        # Wait for the first success
        while futures_map:
            # Check for completed futures
            done, not_done = concurrent.futures.wait(
                futures_map.keys(), return_when=concurrent.futures.FIRST_COMPLETED
            )

            for f in done:
                label, name, temp_path = futures_map.pop(f)
                try:
                    result: ProviderResult = f.result()
                    log.info("Parallel winner: %s Pipeline (%s) succeeded!", label, name)

                    # Copy winner model to requested output path
                    try:
                        import shutil
                        shutil.copyfile(temp_path, glb_path)
                        result.glb_path = glb_path
                    except Exception as e:
                        log.error("Failed to copy parallel model result to target: %s", e)

                    # Clean up temporary files
                    for _, _, p in futures_map.values():
                        try:
                            if os.path.exists(p):
                                os.remove(p)
                        except Exception:
                            pass
                    try:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    except Exception:
                        pass

                    return result
                except Exception as exc:
                    log.warning("%s Pipeline (%s) failed with: %s", label, name, exc)
                    errors.append(f"{label} ({name}): {exc}")
                    try:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    except Exception:
                        pass

            if not futures_map:
                break

            time.sleep(0.5)

        raise ProviderError(
            f"Both parallel pipelines failed: {'; '.join(errors)}"
        )
