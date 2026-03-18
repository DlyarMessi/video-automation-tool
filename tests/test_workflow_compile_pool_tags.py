from __future__ import annotations

import unittest

from src.workflow import compile_creative_dict


class WorkflowCompilePoolTagsTests(unittest.TestCase):
    def test_short_term_demo_tags_match_current_pool_selector_vocabulary(self) -> None:
        creative = {
            "meta": {"target_length": 20},
            "beats": [
                {"purpose": "establish_context", "subtitle": "S1", "vo": "V1", "visual": "factory exterior"},
                {"purpose": "show_capability", "subtitle": "S2", "vo": "V2", "visual": "automation line"},
                {"purpose": "build_trust", "subtitle": "S3", "vo": "V3", "visual": "inspection detail"},
                {"purpose": "brand_close", "subtitle": "S4", "vo": "V4", "visual": "villa elevator hero"},
            ],
        }

        compiled = compile_creative_dict(creative)
        sources = [str(item.get("source") or "") for item in compiled.get("timeline", [])]

        allowed = {
            "next:tags:factory,building,hero",
            "next:tags:factory,line,hero",
            "next:tags:factory,line,medium",
            "next:tags:factory,line,detail",
            "next:tags:factory,building,detail",
            "next:tags:factory,building,medium",
        }
        self.assertTrue(sources)
        self.assertTrue(all(src in allowed for src in sources))
        self.assertTrue(any(src == "next:tags:factory,building,hero" for src in sources))
        self.assertTrue(any(src == "next:tags:factory,line,medium" for src in sources))
        self.assertTrue(any(src == "next:tags:factory,line,detail" for src in sources))
        self.assertTrue(all("orbit" not in src for src in sources))
        self.assertTrue(all("slide" not in src for src in sources))


if __name__ == "__main__":
    unittest.main()
