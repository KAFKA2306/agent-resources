import hashlib
import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = ROOT / "docs" / "dashboard"


class ActivityTimelineAssetsTest(unittest.TestCase):
    def test_dashboard_loads_timeline_enhancement(self):
        html = (DASHBOARD / "index.html").read_text(encoding="utf-8")
        self.assertIn("./activity-timeline.css", html)
        self.assertIn('"activity-timeline.js"', html)
        self.assertIn('id="activity-feed"', html)
        self.assertIn('id="activity-title">最近の活動</h2>', html)

    def test_timeline_keeps_visible_activity_labels(self):
        script = (DASHBOARD / "activity-timeline.js").read_text(encoding="utf-8")
        for label in ("Issue", "Pull Request", "Workflow Run"):
            self.assertIn(label, script)
        self.assertIn("assetFailure", json.dumps(self._manifest()["policy"]))
        self.assertTrue(self._manifest()["policy"]["visibleTextRequired"])

    def test_vendored_sprite_matches_pinned_manifest(self):
        manifest = self._manifest()
        sprite_path = DASHBOARD / manifest["vendor"]["localPath"]
        payload = sprite_path.read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), manifest["source"]["sha256"])
        self.assertNotEqual(manifest["source"]["commit"], "main")
        self.assertNotIn("/main/", manifest["source"]["sourceUrl"])
        ET.fromstring(payload)
        text = payload.decode("utf-8")
        for symbol in manifest["vendor"]["symbols"]:
            self.assertIn(f'id="{symbol}"', text)

    @staticmethod
    def _manifest():
        return json.loads((DASHBOARD / "assets" / "icon-manifest.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
