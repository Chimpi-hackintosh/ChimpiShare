import copy
import datetime as dt
import unittest
from unittest.mock import patch

import support_notice as support


class SupportNoticeTests(unittest.TestCase):
    def test_only_older_known_versions_warn(self):
        for current in ["3.0.1", "3.0.1-build-999", "4.0.0", "garbage", None]:
            self.assertIsNone(support.notice("OpenCore-Helper", current))
        self.assertIsNone(support.notice("Unknown-private-app", "0.0.1"))
        self.assertIsNone(support.notice("ChimpiConstrucoes", "1.0.0"))
        self.assertIsNotNone(support.notice("OpenCore-Helper", "3.0.0"))

    def test_cutoff_is_exact_and_has_a_year(self):
        before = dt.datetime(2026, 11, 3, 23, 59, 59, tzinfo=dt.timezone.utc)
        after = before + dt.timedelta(seconds=1)
        self.assertEqual(support.notice("OpenCore-Helper", "2.0.0", now=before)["phase"], "before")
        self.assertEqual(support.notice("OpenCore-Helper", "2.0.0", now=after)["phase"], "after")
        self.assertIn("2026", support.notice("OpenCore-Helper", "2.0.0", now=before)["body"])

    def test_numeric_comparison_not_lexical(self):
        self.assertGreater(support.version("1.10.0"), support.version("1.9.9"))
        self.assertEqual(support.version("v1.1.0-preview.3"), (1, 1, 0))
        for value in ["1.0", "prefix1.0.0", "1.0.0<script>", "9" * 101, None]:
            self.assertIsNone(support.version(value))

    def test_language_detection_and_fallback(self):
        self.assertEqual(support.language("pt_BR.UTF-8"), "pt")
        self.assertEqual(support.language("en-US"), "en")
        self.assertEqual(support.language("xx-ZZ"), "en")
        for lang in support.MESSAGES:
            for phase, date in [("before", dt.datetime(2026, 11, 1)), ("after", dt.datetime(2026, 11, 4))]:
                item = support.notice("OpenCore-Helper", "2.0.0", now=date, lang=lang)
                self.assertNotIn("{", item["body"])
                self.assertEqual(item["title"], support.MESSAGES[lang][phase])

    def test_untrusted_links_and_downgrades_are_ignored(self):
        for url in ["http://github.com/Chimpi-hackintosh/OpenCore-Helper", "https://evil.test/", "https://github.com/Other/OpenCore-Helper", "https://github.com/Chimpi-hackintosh/Other", "https://github.com@evil.test/Chimpi-hackintosh/OpenCore-Helper"]:
            candidate = copy.deepcopy(support.POLICY)
            candidate["apps"]["OpenCore-Helper"].update(minimum="99.0.0", url=url)
            self.assertEqual(support.checked_policy(candidate), support.POLICY)
        candidate = copy.deepcopy(support.POLICY)
        candidate["apps"]["OpenCore-Helper"]["minimum"] = "1.0.0"
        self.assertEqual(support.checked_policy(candidate), support.POLICY)

    def test_network_failure_uses_bundled_policy(self):
        with patch.object(support, "read_json", side_effect=OSError("offline")):
            self.assertIsNotNone(support.check("OpenCore-Helper", "2.0.0"))
            self.assertIsNone(support.check("OpenCore-Helper", "3.0.1"))
        with patch.object(support, "read_json") as read:
            self.assertIsNone(support.check("Unknown-private-app", "1.0.0"))
            read.assert_not_called()

    def test_release_channels_and_assets(self):
        url = "https://github.com/Chimpi-hackintosh/OpenCore-Helper/releases/tag/v4.0.0"
        candidate = dict(tag_name="v4.0.0", html_url=url, assets=[{}], draft=False, prerelease=False)
        for invalid in [dict(candidate, draft=True), dict(candidate, assets=[]), dict(candidate, prerelease=True), dict(candidate, html_url="https://evil.test/")]:
            self.assertEqual(support.with_releases(support.POLICY, "OpenCore-Helper", [invalid]), support.POLICY)
        result = support.with_releases(support.POLICY, "OpenCore-Helper", [candidate])
        self.assertIsNotNone(support.notice("OpenCore-Helper", "3.0.1", result))
        self.assertEqual(support.release_version("v0.1-lite.3", "lite"), "0.1.3")
        self.assertIsNone(support.release_version("v0.2-games.1", "lite"))

    def test_smoke_flags_never_start_network(self):
        with patch.object(support.sys, "argv", ["app", "--gui-smoke", "report.json"]):
            self.assertFalse(support.enabled())
        with patch.dict(support.os.environ, {"CHIMPI_SUPPORT_CHECK": "0"}):
            self.assertFalse(support.enabled())


if __name__ == "__main__":
    unittest.main()
