from __future__ import annotations

import os
import unittest

from src.script_provider_config import load_deepseek_config


class DeepSeekConfigTests(unittest.TestCase):
    def test_deepseek_defaults(self) -> None:
        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEEPSEEK_API_KEY", None)
            os.environ.pop("DEEPSEEK_MODEL", None)
            os.environ.pop("DEEPSEEK_BASE_URL", None)
            cfg = load_deepseek_config()
        self.assertEqual(cfg.api_key, "")
        self.assertEqual(cfg.model, "deepseek-chat")
        self.assertEqual(cfg.base_url, "https://api.deepseek.com")

    def test_deepseek_env_and_override(self) -> None:
        with unittest.mock.patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "k",
                "DEEPSEEK_MODEL": "deepseek-reasoner",
                "DEEPSEEK_BASE_URL": "https://example.deepseek.local",
            },
            clear=False,
        ):
            cfg = load_deepseek_config(model_override="deepseek-chat")
        self.assertEqual(cfg.api_key, "k")
        self.assertEqual(cfg.model, "deepseek-chat")
        self.assertEqual(cfg.base_url, "https://example.deepseek.local")


if __name__ == "__main__":
    unittest.main()
