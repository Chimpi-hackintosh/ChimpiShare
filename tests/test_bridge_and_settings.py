import ast
import json
import os
import string
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from chimpishare.bridge import StableInbox, diagnose
from chimpishare.errors import ShareError
from chimpishare.security import Invitation, safe_filename
from chimpishare.settings import Translator, load_settings, save_settings

ROOT = Path(__file__).resolve().parent.parent


class BridgeAndSettingsTests(unittest.TestCase):
    def test_invitation_validation(self):
        good = f"chimpishare://192.168.1.2:48765/v1#{'A' * 43}:{'f' * 64}"
        self.assertEqual(Invitation.parse(good).encode(), good)
        invalid = [good.replace("192.168.1.2", "example.com"), good.replace(":48765", ":0"),
                   good.replace("/v1#", "/v2#"), good.replace("/v1#", "/v1?extra=1#"),
                   good.replace("192.168.1.2", "0.0.0.0"), good.replace("192.168.1.2", "224.0.0.1"),
                   good.replace("chimpishare:", "https:"), good[:-1], "", "../file"]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ShareError):
                Invitation.parse(item)

    def test_unsafe_filename_policy(self):
        for name in ["..", "a/b", "a\\b", "bad\x00name", "x" * 221]:
            with self.subTest(name=name), self.assertRaises(ShareError):
                safe_filename(name)
        self.assertEqual(safe_filename("name:stream.png"), "name_stream.png")
        self.assertEqual(safe_filename("LPT1.txt"), "_LPT1.txt")

    def test_review_inbox_filters_temporary_hidden_and_outside_files(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as outside:
            root = Path(folder)
            (root / "good.png").write_bytes(b"ready")
            (root / "incomplete.part").write_bytes(b"partial")
            (root / ".hidden").write_bytes(b"private")
            (Path(outside) / "other.txt").write_bytes(b"outside")
            try:
                (root / "link.txt").symlink_to(Path(outside) / "other.txt")
            except (OSError, NotImplementedError):
                pass
            inbox = StableInbox(root, stable_seconds=0)
            self.assertEqual([(p.name, size) for p, size in inbox.scan()], [("good.png", 5)])

    def test_inbox_requires_stability_and_resets_after_change(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "file.png"
            path.write_bytes(b"one")
            inbox = StableInbox(folder, stable_seconds=3)
            with patch("chimpishare.bridge.time.monotonic", return_value=0):
                self.assertEqual(inbox.scan(), [])
            with patch("chimpishare.bridge.time.monotonic", return_value=4):
                self.assertEqual(inbox.scan(), [(path, 3)])
            path.write_bytes(b"changed")
            with patch("chimpishare.bridge.time.monotonic", return_value=5):
                self.assertEqual(inbox.scan(), [])

    def test_diagnostics_never_claim_airdrop_verification(self):
        with patch("chimpishare.bridge.socket.if_nameindex", return_value=[(1, "awdl0")]), \
                patch("chimpishare.bridge.shutil.which", return_value="/example/tool"):
            report = diagnose()
        self.assertTrue(report["awdl_interface"])
        self.assertFalse(report["airdrop_verified"])

    def test_locale_keys_placeholders_and_ui_coverage(self):
        pt = json.loads((ROOT / "locales/pt-BR.json").read_text("utf-8"))
        en = json.loads((ROOT / "locales/en.json").read_text("utf-8"))
        self.assertEqual(pt.keys(), en.keys())
        formatter = string.Formatter()
        for key in pt:
            fields = lambda text: {field for _, field, _, _ in formatter.parse(text) if field}
            self.assertEqual(fields(pt[key]), fields(en[key]), key)
        for source in (ROOT / "chimpishare").glob("*.py"):
            for node in ast.walk(ast.parse(source.read_text("utf-8"))):
                if isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
                    is_translation = ((isinstance(node.func, ast.Attribute) and node.func.attr == "t")
                                      or (isinstance(node.func, ast.Name) and node.func.id == "t")
                                      or (isinstance(node.func, ast.Name) and node.func.id == "ShareError"))
                    if is_translation and isinstance(node.args[0].value, str):
                        self.assertIn(node.args[0].value, en, str(source))

    def test_saved_language_override_and_fallback(self):
        with patch("chimpishare.settings.ui_languages", return_value=["fr-FR", "pt-PT"]):
            self.assertEqual(Translator("system").language, "pt-BR")
            self.assertEqual(Translator("en").language, "en")
        self.assertEqual(Translator("ja-JP").language, "en")

    def test_settings_persist_and_bad_values_preserve_defaults(self):
        with tempfile.TemporaryDirectory() as folder, patch("chimpishare.settings.config_dir", return_value=Path(folder)):
            settings = load_settings()
            settings["language"] = "pt-BR"
            save_settings(settings)
            self.assertEqual(load_settings()["language"], "pt-BR")
            (Path(folder) / "settings.json").write_text('{"port":"bad", "language":"en"}', "utf-8")
            self.assertEqual(load_settings()["port"], 48765)
            (Path(folder) / "settings.json").write_text("invalid", "utf-8")
            self.assertEqual(load_settings()["language"], "system")


if __name__ == "__main__":
    unittest.main()
