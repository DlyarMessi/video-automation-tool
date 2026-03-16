from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.ui_local_prefs import clear_last_company, load_ui_local_prefs, remember_last_company


class UILocalPrefsTests(unittest.TestCase):
    def test_remember_and_clear_last_company(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            remember_last_company(root, "Northwind")
            prefs = load_ui_local_prefs(root)
            self.assertEqual(prefs.last_company, "Northwind")

            clear_last_company(root)
            prefs_after_clear = load_ui_local_prefs(root)
            self.assertEqual(prefs_after_clear.last_company, "")


if __name__ == "__main__":
    unittest.main()
