import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLD_JS = ROOT / "docs" / "dashboard" / "world.js"
WORLD_CSS = ROOT / "docs" / "dashboard" / "world.css"


class SiteIconTest(unittest.TestCase):
    def test_public_links_try_the_sites_own_favicon_without_replacing_text(self):
        js = WORLD_JS.read_text(encoding="utf-8")
        css = WORLD_CSS.read_text(encoding="utf-8").replace(" ", "")

        self.assertIn("function createSurfaceIcon(publicUrl)", js)
        self.assertIn('image.src = new URL("favicon.ico", base).href;', js)
        self.assertIn('image.referrerPolicy = "no-referrer";', js)
        self.assertIn("image.hidden = true", js)
        self.assertIn('anchor.textContent = link.kind === "pages" ? "PAGES ↗" : "FRONT ↗";', js)
        self.assertIn("if (icon) anchor.prepend(icon);", js)
        self.assertIn(".world-surface-icon{width:14px;height:14px", css)
        self.assertIn(".world-surface-icon[hidden]{display:none}", css)


if __name__ == "__main__":
    unittest.main()
