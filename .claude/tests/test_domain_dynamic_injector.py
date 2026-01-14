import json
import unittest
from unittest.mock import patch, MagicMock
import importlib.util
import pathlib


HOOK_PATH = pathlib.Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "UserPromptSubmit" / "domain_dynamic_injector.py"


def load_hook_module():
    spec = importlib.util.spec_from_file_location("domain_dynamic_injector", str(HOOK_PATH))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class DomainInjectorTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_hook_module()

    def test_normalize_domain_valid(self):
        self.assertEqual(self.mod._normalize_domain("python"), "python")
        self.assertEqual(self.mod._normalize_domain("JS"), "javascript")

    def test_normalize_domain_invalid(self):
        self.assertIsNone(self.mod._normalize_domain(""))
        self.assertIsNone(self.mod._normalize_domain(".."))
        self.assertIsNone(self.mod._normalize_domain("with spaces"))

    def test_extract_domain_override(self):
        override, stripped = self.mod._extract_domain_override("please do X /domain:math now")
        self.assertEqual(override, "math")
        self.assertNotIn("/domain:math", stripped)

    def test_validate_template_bounds(self):
        settings = self.mod.Settings(template_min_chars=5, template_max_chars=100)
        self.assertFalse(self.mod._validate_template(settings, "a\nb\nc"))  # too short
        self.assertTrue(self.mod._validate_template(settings, "line1\nline2\nline3\nline4\nline5"))

    @patch.object(pathlib.Path, "read_text", side_effect=FileNotFoundError())
    def test_is_enabled_default_false(self, _):
        self.assertFalse(self.mod._is_enabled())

    @patch("requests.post")
    def test_anthropic_detect_domain_parsing(self, post):
        settings = self.mod.Settings()
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"content": [{"text": "finance"}]}
        post.return_value = resp

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "x"}):
            domain = self.mod._anthropic_detect_domain(settings, "prompt")
        self.assertEqual(domain, "finance")

    @patch("requests.post")
    def test_grok_generate_template_parsing(self, post):
        settings = self.mod.Settings()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"choices": [{"message": {"content": "TEMPLATE\nline2\nline3\nline4"}}]}
        post.return_value = resp

        with patch.dict("os.environ", {"GROK_API_KEY": "x"}):
            out = self.mod._grok_generate_template(settings, "finance", "meta")
        self.assertIn("TEMPLATE", out)

    def test_cache_key_stable(self):
        k1 = self.mod._cache_key("meta", "model")
        k2 = self.mod._cache_key("meta", "model")
        self.assertEqual(k1, k2)

    def test_pii_redact_default_patterns(self):
        s, changed = self.mod._pii_redact("email me at a@b.com and token=SECRET")
        self.assertTrue(changed)
        self.assertNotIn("a@b.com", s)
        self.assertNotIn("SECRET", s)


if __name__ == "__main__":
    unittest.main()