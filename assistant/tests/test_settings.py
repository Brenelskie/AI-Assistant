import os
import runpy
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

SETTINGS_PATH = Path(__file__).resolve().parents[2] / "config" / "settings.py"


class EnvironmentSettingsTests(SimpleTestCase):
    def read_settings(self, **values):
        with patch.dict(os.environ, values):
            return runpy.run_path(str(SETTINGS_PATH))

    def test_development_starts_without_provider_key_or_database(self):
        settings = self.read_settings(DJANGO_ENV="development", GEMINI_API_KEY="")
        self.assertTrue(settings["DEBUG"])
        self.assertEqual(settings["GEMINI_API_KEY"], "")
        self.assertEqual(settings["DATABASES"], {})

    def test_production_requires_a_private_secret(self):
        for secret in ("", "short", "django-insecure-" + "x" * 70):
            with self.subTest(secret_type=secret[:15]):
                with self.assertRaises(ImproperlyConfigured):
                    self.read_settings(DJANGO_ENV="production", DJANGO_SECRET_KEY=secret)

    def test_production_requires_allowed_hosts(self):
        with self.assertRaises(ImproperlyConfigured):
            self.read_settings(
                DJANGO_ENV="production", DJANGO_SECRET_KEY="private-test-secret-" * 4,
                DJANGO_ALLOWED_HOSTS="",
            )

    def test_valid_production_uses_https_and_disables_debug(self):
        settings = self.read_settings(
            DJANGO_ENV="production", DJANGO_SECRET_KEY="private-test-secret-" * 4,
            DJANGO_ALLOWED_HOSTS="example.com", DJANGO_BEHIND_HTTPS_PROXY="True",
        )
        self.assertFalse(settings["DEBUG"])
        self.assertEqual(settings["ALLOWED_HOSTS"], ["example.com"])
        self.assertTrue(settings["CSRF_COOKIE_SECURE"])
        self.assertTrue(settings["SECURE_SSL_REDIRECT"])
