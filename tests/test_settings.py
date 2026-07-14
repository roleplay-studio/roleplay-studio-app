"""Tests for Settings — focus on derived paths and DB URL helpers."""

from pathlib import Path

from app.infrastructure.config import Settings


class TestAvatarsDir:
    def test_avatars_dir_points_to_uploads_avatars(self):
        """avatars_dir must point to the same location api.constants.UPLOADS_DIR uses.

        Otherwise the upload route, the bot-import service, and the export
        endpoint would read/write from different physical locations — a
        silent bug where exports produce placeholders instead of the real
        avatar.
        """
        settings = Settings.from_env()
        expected = settings.__class__.__module__  # just to make the import obviously used
        from api.constants import UPLOADS_DIR

        assert isinstance(settings.avatars_dir, Path)
        # Compare resolved paths so a relative ``UPLOAD_DIR`` (e.g.
        # ``uploads``) and an absolute one resolve to the same string
        # when they actually point at the same on-disk location.
        assert settings.avatars_dir.resolve() == Path(UPLOADS_DIR).resolve(), (
            f"avatars_dir={settings.avatars_dir} != UPLOADS_DIR={UPLOADS_DIR}"
        )
        del expected  # silence linter


class TestVersion:
    """The version field must read from pyproject.toml (SSOT) and be
    override-able via APP_VERSION env var for packaged builds."""

    def test_default_version_matches_pyproject(self, monkeypatch):
        """Without APP_VERSION set, version comes from package metadata
        which mirrors pyproject.toml [project].version."""
        monkeypatch.delenv("APP_VERSION", raising=False)
        settings = Settings.from_env()
        assert settings.version == "0.1.0", (
            f"Expected version to mirror pyproject.toml (0.1.0), got {settings.version!r}. "
            "If you bumped version in pyproject.toml, the SSOT is broken."
        )

    def test_app_version_env_overrides(self, monkeypatch):
        """APP_VERSION env var wins over package metadata. Useful for
        PyInstaller binaries where pyproject metadata may be unavailable."""
        monkeypatch.setenv("APP_VERSION", "0.2.0-rc1")
        settings = Settings.from_env()
        assert settings.version == "0.2.0-rc1"

    def test_class_default_uses_package_metadata(self):
        """Constructing Settings() with no args (not via from_env) still
        produces a version from package metadata, not the placeholder."""
        settings = Settings()
        assert settings.version == "0.1.0"
        assert settings.version != "0.0.0+unknown"


class TestDebugEnabled:
    """Controls whether LLM debug payloads (real prompt + token counts)
    are surfaced in the dev-mode chat modal.

    Gating rules (deliberately permissive in dev, strict in prod):
      - DEBUG=true            → on
      - ENVIRONMENT=development → on
      - anything else         → off
    """

    def test_default_off(self, monkeypatch):
        monkeypatch.delenv("DEBUG", raising=False)
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        settings = Settings.from_env()
        assert settings.debug_enabled is False

    def test_debug_true_turns_on(self, monkeypatch):
        monkeypatch.setenv("DEBUG", "true")
        settings = Settings.from_env()
        assert settings.debug_enabled is True

    def test_environment_development_turns_on(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        settings = Settings.from_env()
        assert settings.debug_enabled is True

    def test_debug_false_keeps_off(self, monkeypatch):
        monkeypatch.setenv("DEBUG", "false")
        settings = Settings.from_env()
        assert settings.debug_enabled is False

    def test_debug_truthy_value_turns_on(self, monkeypatch):
        """Any non-"false" value (1, yes, on) is treated as truthy, matching
        the rest of the Settings env-parsing convention in this module."""
        monkeypatch.setenv("DEBUG", "1")
        settings = Settings.from_env()
        assert settings.debug_enabled is True


class TestLlmProviderValidator:
    """Settings.llm_provider accepts any id from api.constants.PROVIDERS + 'mock',
    and silently falls back to 'mock' for unknown ids."""

    def test_accepts_every_known_provider(self, monkeypatch):
        from api.constants import PROVIDERS

        for pid in (*list(PROVIDERS.keys()), "mock"):
            monkeypatch.setenv("LLM_PROVIDER", pid)
            s = Settings.from_env()
            assert s.llm_provider == pid, f"expected {pid!r}, got {s.llm_provider!r}"

    def test_unknown_provider_falls_back_to_mock(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "not-a-real-provider")
        s = Settings.from_env()
        assert s.llm_provider == "mock"

    def test_default_is_openrouter(self, monkeypatch):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        s = Settings.from_env()
        assert s.llm_provider == "openrouter"

    def test_normalises_case_and_whitespace(self, monkeypatch):
        # Edge case: PROVIDERS keys are lowercase. A user typing
        # "OpenRouter" or "  openrouter  " should still match.
        monkeypatch.setenv("LLM_PROVIDER", "  OpenRouter  ")
        s = Settings.from_env()
        assert s.llm_provider == "openrouter"

    def test_non_string_falls_back_to_mock(self, monkeypatch):
        # Defensive: a bool/None slipping through (e.g. from a
        # mis-coded default) should not crash — fall back to mock.
        monkeypatch.setenv("LLM_PROVIDER", "")
        s = Settings.from_env()
        assert s.llm_provider == "mock"
