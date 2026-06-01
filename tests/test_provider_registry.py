"""Tests for the image-to-3D provider registry."""
from __future__ import annotations

import pytest

from server.providers.registry import PROVIDERS, get_provider, list_provider_status
from server.providers.base import ProviderError, ProviderNotConfigured


EXPECTED_PROVIDERS = {"meshy", "tripo", "rodin", "hunyuan3d", "local_command"}


class TestProviderRegistryContents:
    def test_all_expected_providers_registered(self):
        for name in EXPECTED_PROVIDERS:
            assert name in PROVIDERS, f"Provider '{name}' missing from registry"

    def test_provider_names_are_lowercase(self):
        for name in PROVIDERS:
            assert name == name.lower(), f"Provider key '{name}' should be lowercase"

    def test_get_provider_returns_correct_instance(self):
        for name in EXPECTED_PROVIDERS:
            provider = get_provider(name)
            assert provider.name == name

    def test_get_provider_raises_on_unknown(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("totally_fake_provider")

    def test_get_provider_case_insensitive(self):
        # get_provider normalises the name
        p = get_provider("MESHY")
        assert p.name == "meshy"


class TestProviderStatus:
    def test_list_provider_status_returns_list(self):
        statuses = list_provider_status()
        assert isinstance(statuses, list)
        assert len(statuses) == len(PROVIDERS)

    def test_each_status_has_required_keys(self):
        for status in list_provider_status():
            assert "name" in status, f"Status missing 'name': {status}"
            assert "configured" in status, f"Status missing 'configured': {status}"

    def test_unconfigured_providers_not_configured(self, monkeypatch):
        """Without any env vars set, cloud providers should not be configured."""
        for key in [
            "MESHY_API_KEY", "REMIRDY_MESHY_API_KEY",
            "TRIPO_API_KEY", "REMIRDY_TRIPO_API_KEY",
            "RODIN_API_KEY", "REMIRDY_RODIN_API_KEY",
            "HUNYUAN3D_API_KEY",
        ]:
            monkeypatch.delenv(key, raising=False)

        cloud_names = {"meshy", "tripo", "rodin", "hunyuan3d"}
        for status in list_provider_status():
            if status["name"] in cloud_names:
                assert status["configured"] is False, (
                    f"Provider '{status['name']}' should be unconfigured without env vars"
                )


class TestProviderInterface:
    def test_each_provider_has_generate_method(self):
        for provider in PROVIDERS.values():
            assert callable(getattr(provider, "generate", None))

    def test_each_provider_has_is_configured_method(self):
        for provider in PROVIDERS.values():
            assert callable(getattr(provider, "is_configured", None))

    def test_each_provider_has_missing_config_method(self):
        for provider in PROVIDERS.values():
            assert callable(getattr(provider, "missing_config", None))

    def test_missing_config_returns_list(self):
        for provider in PROVIDERS.values():
            result = provider.missing_config()
            assert isinstance(result, list)
