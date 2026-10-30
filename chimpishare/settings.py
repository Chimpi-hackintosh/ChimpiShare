import ctypes
import json
import locale
import os
import sys
from pathlib import Path


def resource_path(name):
    if getattr(sys, "frozen", False):
        external = Path(sys.executable).parent / name
        if external.exists():
            return external
        return Path(sys._MEIPASS) / name
    return Path(__file__).resolve().parent.parent / name


def config_dir():
    if sys.platform == "win32":
        buffer = ctypes.create_unicode_buffer(32768)
        # CSIDL_LOCAL_APPDATA: ask Windows instead of assuming a drive or user.
        if ctypes.windll.shell32.SHGetFolderPathW(None, 28, None, 0, buffer) != 0:
            raise OSError("SHGetFolderPathW failed")
        root = Path(buffer.value) / "SnoopyOS Company"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / "SnoopyOS Company"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "ChimpiShare"


def load_settings():
    defaults = json.loads(resource_path("settings.default.json").read_text("utf-8"))
    try:
        saved = json.loads((config_dir() / "settings.json").read_text("utf-8"))
        if isinstance(saved, dict):
            for key in defaults:
                if key in saved and type(saved[key]) is type(defaults[key]):
                    defaults[key] = saved[key]
    except (OSError, ValueError):
        pass
    return defaults


def save_settings(values):
    folder = config_dir()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = folder / "settings.json.tmp"
    temp.write_text(json.dumps(values, indent=2, ensure_ascii=False), "utf-8")
    os.replace(temp, folder / "settings.json")


def ui_languages():
    if sys.platform == "win32":
        count, length = ctypes.c_ulong(), ctypes.c_ulong()
        fn = ctypes.windll.kernel32.GetUserPreferredUILanguages
        if fn(8, ctypes.byref(count), None, ctypes.byref(length)) and length.value:
            buffer = ctypes.create_unicode_buffer(length.value)
            if fn(8, ctypes.byref(count), buffer, ctypes.byref(length)):
                return [s for s in buffer[:length.value].split("\0") if s]
        lang = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return [locale.windows_locale.get(lang, "en")]
    return [os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES")
            or os.environ.get("LANG") or locale.getlocale()[0] or "en"]


class Translator:
    def __init__(self, override="system"):
        candidates = ui_languages() if override == "system" else [override]
        self.language = "en"
        for candidate in candidates:
            normalized = candidate.replace("_", "-").split(".")[0].lower()
            if normalized.startswith("pt"):
                self.language = "pt-BR"
                break
            if normalized.startswith("en"):
                break
        self.strings = json.loads(resource_path(f"locales/{self.language}.json").read_text("utf-8"))

    def __call__(self, key, **values):
        return self.strings.get(key, key).format(**values)
