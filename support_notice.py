"""Non-blocking, read-only support checks for Chimpi desktop applications.

No telemetry, automatic downloads, credentials, installation or forced exit.
Policy and messages are bundled so an offline startup remains useful.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import locale
import os
import queue
import re
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser

POLICY = {'schema': 1, 'verified_at': '2026-11-01', 'ends_at': '2026-11-04T00:00:00Z', 'table': 'https://chimpi-hackintosh.github.io/ChimpiBlender-Online/support.html', 'apps': {'OpenCore-Helper': {'name': 'OpenCore Helper', 'repo': 'OpenCore-Helper', 'minimum': '3.0.1', 'tag': 'v3.0.1', 'preview': False, 'edition': None, 'url': 'https://github.com/Chimpi-hackintosh/OpenCore-Helper/releases/tag/v3.0.1', 'status': 'published'}, 'SnoopyOS-Lite': {'name': 'SnoopyOS Lite', 'repo': 'SnoopyOS-Image', 'minimum': '0.1.3', 'tag': 'v0.1-lite.3', 'preview': True, 'edition': 'lite', 'url': 'https://github.com/Chimpi-hackintosh/SnoopyOS-Image/releases/tag/v0.1-lite.3', 'status': 'preview'}, 'SnoopyOS-Games': {'name': 'SnoopyOS Games', 'repo': 'SnoopyOS-Image', 'minimum': '0.2.1', 'tag': 'v0.2-games.1', 'preview': True, 'edition': 'games', 'url': 'https://github.com/Chimpi-hackintosh/SnoopyOS-Image/releases/tag/v0.2-games.1', 'status': 'preview'}, 'ChimpiAI': {'name': 'ChimpiAI', 'repo': 'ChimpiAI', 'minimum': '1.0.0', 'tag': 'ChimpiAI-1.0.0-beta', 'preview': True, 'edition': None, 'url': 'https://github.com/Chimpi-hackintosh/ChimpiAI/releases/tag/ChimpiAI-1.0.0-beta', 'status': 'preview'}, 'WinSIMU': {'name': 'WinSIMU', 'repo': 'WinSIMU', 'minimum': '0.1.0', 'tag': 'v0.1.0-alpha', 'preview': True, 'edition': None, 'url': 'https://github.com/Chimpi-hackintosh/WinSIMU/releases/tag/v0.1.0-alpha', 'status': 'preview'}, 'ChimpiCode': {'name': 'ChimpiCode', 'repo': 'ChimpiCode', 'minimum': '1.1.0', 'tag': 'v1.1.0-preview.3', 'preview': True, 'edition': None, 'url': 'https://github.com/Chimpi-hackintosh/ChimpiCode/releases/tag/v1.1.0-preview.3', 'status': 'preview'}, 'ChimpiBridge': {'name': 'ChimpiBridge', 'repo': 'ChimpiBridge', 'minimum': '0.1.1', 'tag': 'v0.1.1', 'preview': True, 'edition': None, 'url': 'https://github.com/Chimpi-hackintosh/ChimpiBridge/releases/tag/v0.1.1', 'status': 'preview'}, 'ChimpiShare': {'name': 'ChimpiShare', 'repo': 'ChimpiShare', 'minimum': '0.1.0', 'tag': 'v0.1.0', 'preview': True, 'edition': None, 'url': 'https://github.com/Chimpi-hackintosh/ChimpiShare/releases/tag/v0.1.0', 'status': 'preview'}, 'ChimpiConstrucoes': {'name': 'ChimpiConstruções', 'repo': 'ChimpiConstrucoes', 'minimum': None, 'tag': None, 'preview': True, 'edition': None, 'url': 'https://github.com/Chimpi-hackintosh/ChimpiConstrucoes', 'status': 'source'}, 'ChimpiBlender-Online': {'name': 'ChimpiBlender Online', 'repo': 'ChimpiBlender-Online', 'minimum': None, 'tag': None, 'preview': False, 'edition': None, 'url': 'https://chimpi-hackintosh.github.io/ChimpiBlender-Online/', 'status': 'website', 'web_revision': 20261101}, 'ChimpiNotch': {'name': 'ChimpiNotch', 'repo': 'ChimpiNotch', 'minimum': '1.0.4', 'tag': 'v1.0.4', 'preview': False, 'edition': None, 'url': 'https://github.com/Chimpi-hackintosh/ChimpiNotch/releases/tag/v1.0.4', 'status': 'published'}, 'Chimpi3D-Installer': {'name': 'Chimpi3D', 'repo': 'Chimpi3D-Installer', 'minimum': '0.3.1', 'tag': 'v0.3.1-build-11', 'preview': False, 'edition': None, 'url': 'https://github.com/Chimpi-hackintosh/Chimpi3D-Installer/releases/tag/v0.3.1-build-11', 'status': 'published'}, 'ChimpiNFC': {'name': 'ChimpiNFC', 'repo': 'ChimpiNFC', 'minimum': '0.1.0', 'tag': 'v0.1.0-build-2', 'preview': True, 'edition': None, 'url': 'https://github.com/Chimpi-hackintosh/ChimpiNFC/releases/tag/v0.1.0-build-2', 'status': 'preview'}}}
MESSAGES = {'en': {'before': 'Your version is about to lose support', 'after': 'Your version no longer receives security updates', 'body_before': 'Older versions of {app} will stop receiving security updates on 4 November 2026', 'body_after': 'Older versions of {app} have not received security updates since 4 November 2026', 'risk': 'Software without security fixes may remain exposed to vulnerabilities — update from the official project page', 'versions': 'Installed: {current} · Minimum supported: {minimum} · Available: {latest}', 'update': 'Update', 'later': 'Later', 'table': 'Apps and support', 'app': 'App / website', 'available': 'Available version', 'support': 'Support / action', 'published': 'Published', 'preview': 'Preview — may be unstable', 'source': 'No downloadable release — no upgrade required yet', 'website': 'Website — reload for the latest code', 'intro': 'Versions below those listed lose security support on 4 November 2026 — the date is 00:00 UTC', 'intro_after': 'Versions below those listed no longer receive security updates as of 4 November 2026 at 00:00 UTC', 'legacy': 'Already installed versions without an update checker need a manual update — this notice does not imply an infection or install anything automatically', 'footer': 'Catalog verified on {date} — release links are official, source changes awaiting review are not new releases'}, 'pt': {'before': 'Sua versão está prestes a não ser suportada', 'after': 'Sua versão não recebe mais atualizações de segurança', 'body_before': 'As versões antigas do {app} deixarão de receber atualizações de segurança em 4 de novembro de 2026', 'body_after': 'As versões antigas do {app} não recebem atualizações de segurança desde 4 de novembro de 2026', 'risk': 'Software sem correções de segurança pode ficar exposto a falhas — atualize pela página oficial do projeto', 'versions': 'Instalada: {current} · Mínima suportada: {minimum} · Disponível: {latest}', 'update': 'Atualizar', 'later': 'Depois', 'table': 'Apps e suporte', 'app': 'App / site', 'available': 'Versão disponível', 'support': 'Suporte / ação', 'published': 'Publicada', 'preview': 'Prévia — pode ter instabilidade', 'source': 'Sem lançamento para download — ainda sem atualização exigida', 'website': 'Site — recarregue para receber o código atual', 'intro': 'Versões abaixo das listadas perdem o suporte de segurança em 4 de novembro de 2026, às 00h UTC', 'intro_after': 'Versões abaixo das listadas não recebem atualizações de segurança desde 4 de novembro de 2026, às 00h UTC', 'legacy': 'Versões já instaladas sem verificador precisam de atualização manual — este aviso não indica infecção nem instala nada automaticamente', 'footer': 'Catálogo conferido em {date} — os links são oficiais e alterações aguardando revisão ainda não são novos lançamentos'}, 'es': {'before': 'Tu versión está a punto de perder soporte', 'after': 'Tu versión ya no recibe actualizaciones de seguridad', 'body_before': 'Las versiones antiguas de {app} dejarán de recibir actualizaciones de seguridad el 4 de noviembre de 2026', 'body_after': 'Las versiones antiguas de {app} no reciben actualizaciones de seguridad desde el 4 de noviembre de 2026', 'risk': 'El software sin correcciones de seguridad puede quedar expuesto a vulnerabilidades — actualiza desde la página oficial', 'versions': 'Instalada: {current} · Mínima compatible: {minimum} · Disponible: {latest}', 'update': 'Actualizar', 'later': 'Más tarde', 'table': 'Apps y soporte'}, 'fr': {'before': 'Votre version va bientôt perdre son support', 'after': 'Votre version ne reçoit plus de mises à jour de sécurité', 'body_before': 'Les anciennes versions de {app} ne recevront plus de mises à jour de sécurité à partir du 4 novembre 2026', 'body_after': 'Les anciennes versions de {app} ne reçoivent plus de mises à jour de sécurité depuis le 4 novembre 2026', 'risk': 'Un logiciel sans correctifs de sécurité peut rester vulnérable — mettez-le à jour depuis la page officielle', 'versions': 'Installée : {current} · Minimum pris en charge : {minimum} · Disponible : {latest}', 'update': 'Mettre à jour', 'later': 'Plus tard', 'table': 'Apps et support'}, 'de': {'before': 'Deine Version wird bald nicht mehr unterstützt', 'after': 'Deine Version erhält keine Sicherheitsupdates mehr', 'body_before': 'Ältere Versionen von {app} erhalten ab dem 4. November 2026 keine Sicherheitsupdates mehr', 'body_after': 'Ältere Versionen von {app} erhalten seit dem 4. November 2026 keine Sicherheitsupdates mehr', 'risk': 'Software ohne Sicherheitskorrekturen kann angreifbar bleiben — aktualisiere sie über die offizielle Projektseite', 'versions': 'Installiert: {current} · Unterstütztes Minimum: {minimum} · Verfügbar: {latest}', 'update': 'Aktualisieren', 'later': 'Später', 'table': 'Apps und Support'}, 'it': {'before': 'La tua versione sta per perdere il supporto', 'after': 'La tua versione non riceve più aggiornamenti di sicurezza', 'body_before': 'Le versioni precedenti di {app} non riceveranno più aggiornamenti di sicurezza dal 4 novembre 2026', 'body_after': 'Le versioni precedenti di {app} non ricevono aggiornamenti di sicurezza dal 4 novembre 2026', 'risk': 'Il software senza correzioni di sicurezza può restare vulnerabile — aggiorna dalla pagina ufficiale', 'versions': 'Installata: {current} · Minima supportata: {minimum} · Disponibile: {latest}', 'update': 'Aggiorna', 'later': 'Più tardi', 'table': 'App e supporto'}, 'ru': {'before': 'Поддержка вашей версии скоро закончится', 'after': 'Ваша версия больше не получает обновления безопасности', 'body_before': 'Старые версии {app} перестанут получать обновления безопасности 4 ноября 2026 года', 'body_after': 'Старые версии {app} не получают обновления безопасности с 4 ноября 2026 года', 'risk': 'Программы без исправлений безопасности могут оставаться уязвимыми — обновитесь с официальной страницы проекта', 'versions': 'Установлена: {current} · Минимальная поддерживаемая: {minimum} · Доступна: {latest}', 'update': 'Обновить', 'later': 'Позже', 'table': 'Приложения и поддержка'}, 'zh': {'before': '你的版本即将停止支持', 'after': '你的版本已停止接收安全更新', 'body_before': '{app} 的旧版本将于 2026 年 11 月 4 日停止接收安全更新', 'body_after': '{app} 的旧版本自 2026 年 11 月 4 日起不再接收安全更新', 'risk': '缺少安全修复的软件可能仍存在漏洞，请通过项目官方页面更新', 'versions': '已安装：{current} · 最低支持版本：{minimum} · 可用版本：{latest}', 'update': '更新', 'later': '稍后', 'table': '应用与支持'}, 'ja': {'before': 'このバージョンのサポートはまもなく終了します', 'after': 'このバージョンのセキュリティ更新は終了しました', 'body_before': '{app} の旧バージョンは2026年11月4日にセキュリティ更新を終了します', 'body_after': '{app} の旧バージョンは2026年11月4日以降セキュリティ更新を受け取れません', 'risk': '修正のないソフトウェアには脆弱性が残る可能性があります — 公式ページから更新してください', 'versions': 'インストール済み：{current} · 最低サポート：{minimum} · 利用可能：{latest}', 'update': '更新', 'later': '後で', 'table': 'アプリとサポート'}, 'ko': {'before': '현재 버전의 지원이 곧 종료됩니다', 'after': '현재 버전은 더 이상 보안 업데이트를 받지 않습니다', 'body_before': '{app}의 이전 버전은 2026년 11월 4일부터 보안 업데이트를 받지 않습니다', 'body_after': '{app}의 이전 버전은 2026년 11월 4일 이후 보안 업데이트가 중단되었습니다', 'risk': '보안 수정이 없는 소프트웨어는 취약할 수 있습니다 — 공식 프로젝트 페이지에서 업데이트하세요', 'versions': '설치됨: {current} · 최소 지원: {minimum} · 사용 가능: {latest}', 'update': '업데이트', 'later': '나중에', 'table': '앱 및 지원'}, 'ar': {'before': 'سيتوقف دعم إصدارك قريبًا', 'after': 'لم يعد إصدارك يتلقى تحديثات الأمان', 'body_before': 'ستتوقف الإصدارات القديمة من {app} عن تلقي تحديثات الأمان في 4 نوفمبر 2026', 'body_after': 'لم تعد الإصدارات القديمة من {app} تتلقى تحديثات الأمان منذ 4 نوفمبر 2026', 'risk': 'قد تظل البرامج دون إصلاحات أمنية عرضة للثغرات — حدّث من صفحة المشروع الرسمية', 'versions': 'المثبت: {current} · الحد الأدنى المدعوم: {minimum} · المتاح: {latest}', 'update': 'تحديث', 'later': 'لاحقًا', 'table': 'التطبيقات والدعم'}, 'hi': {'before': 'आपके संस्करण का समर्थन जल्द समाप्त होगा', 'after': 'आपके संस्करण को अब सुरक्षा अपडेट नहीं मिलते', 'body_before': '{app} के पुराने संस्करणों को 4 नवंबर 2026 से सुरक्षा अपडेट नहीं मिलेंगे', 'body_after': '{app} के पुराने संस्करणों को 4 नवंबर 2026 से सुरक्षा अपडेट नहीं मिल रहे हैं', 'risk': 'सुरक्षा सुधारों के बिना सॉफ़्टवेयर असुरक्षित रह सकता है — आधिकारिक परियोजना पेज से अपडेट करें', 'versions': 'इंस्टॉल किया गया: {current} · न्यूनतम समर्थित: {minimum} · उपलब्ध: {latest}', 'update': 'अपडेट करें', 'later': 'बाद में', 'table': 'ऐप और समर्थन'}}
POLICY_URL = "https://raw.githubusercontent.com/Chimpi-hackintosh/ChimpiBlender-Online/main/support-policy.json"
MAX_BYTES = 262144


def language(tag=None):
    if tag is None:
        tag = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG")
        try:
            if sys.platform == "win32":
                import ctypes
                buffer = ctypes.create_unicode_buffer(85)
                if ctypes.windll.kernel32.GetUserDefaultLocaleName(buffer, len(buffer)):
                    tag = buffer.value
            elif sys.platform == "darwin":
                tag = subprocess.check_output(["defaults", "read", "-g", "AppleLanguages"],
                                              timeout=2, stderr=subprocess.DEVNULL).decode()
                match = re.search(r"[a-z]{2,3}(?:[-_][A-Za-z]{2,4})?", tag)
                tag = match.group() if match else None
            if not tag:
                tag = locale.getlocale()[0]
        except (OSError, ValueError, subprocess.SubprocessError, AttributeError):
            pass
    code = str(tag or "en").replace("_", "-").split("-")[0].split(".")[0].lower()
    return code if code in MESSAGES else "en"


def texts(tag=None):
    return dict(MESSAGES["en"], **MESSAGES[language(tag)])


def version(value):
    """Compare the app's release series, not CI build suffixes or preview labels."""
    if not isinstance(value, str) or len(value) > 100:
        return None
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:[-+][A-Za-z0-9.-]+)?", value)
    return tuple(map(int, match.group(1, 2, 3))) if match else None


def official_url(url, repo=None, table=False):
    if not isinstance(url, str):
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme != "https" or parsed.username or parsed.password or port not in (None, 443):
        return False
    if table:
        return parsed.netloc == "chimpi-hackintosh.github.io" and parsed.path == "/ChimpiBlender-Online/support.html" and not parsed.query and not parsed.fragment
    parts = parsed.path.strip("/").split("/")
    return (parsed.netloc == "github.com" and len(parts) >= 2 and
            parts[0] == "Chimpi-hackintosh" and (repo is None or parts[1] == repo) and
            not parsed.query and not parsed.fragment and all(part not in (".", "..") for part in parts))


def read_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Chimpi-support-check/1", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=4) as response:
        # Never follow a GitHub redirect to a different host for policy data.
        if urllib.parse.urlparse(response.geturl()).hostname != urllib.parse.urlparse(url).hostname:
            raise ValueError("Unexpected redirect")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Oversized response")
    return json.loads(raw)


def checked_policy(candidate, bundled=POLICY):
    """Accept valid entries only for known apps; preserve usable offline entries."""
    result = copy.deepcopy(bundled)
    if not isinstance(candidate, dict) or candidate.get("schema") != 1 or not isinstance(candidate.get("apps"), dict):
        return result
    # The owner's declared cutoff is immutable in this release of the checker.
    for key, original in bundled["apps"].items():
        entry = candidate["apps"].get(key)
        if not isinstance(entry, dict) or entry.get("repo") != original["repo"]:
            continue
        new, old = version(entry.get("minimum")), version(original.get("minimum"))
        if new is None or (old is not None and new < old):
            continue
        if not official_url(entry.get("url"), original["repo"]):
            continue
        result["apps"][key].update(minimum=entry["minimum"], tag=str(entry.get("tag") or entry["minimum"])[:100], url=entry["url"])
    return result


def release_version(tag, edition=None):
    if not isinstance(tag, str):
        return None
    if edition:
        match = re.fullmatch(r"v(\d+)\.(\d+)-" + re.escape(edition) + r"\.(\d+)", tag)
        return ".".join(match.groups()) if match else None
    match = re.search(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$", tag)
    return match.group() if match else None


def with_releases(policy, app, releases):
    result = copy.deepcopy(policy)
    entry = result["apps"].get(app)
    if entry is None or not isinstance(releases, list):
        return result
    for release in releases[:30]:
        if not isinstance(release, dict) or release.get("draft") or not release.get("assets"):
            continue
        if release.get("prerelease") and not entry.get("preview"):
            continue
        value = release_version(release.get("tag_name"), entry.get("edition"))
        parsed = version(value)
        if parsed is None or (version(entry.get("minimum")) is not None and parsed <= version(entry["minimum"])):
            continue
        if official_url(release.get("html_url"), entry["repo"]):
            entry.update(minimum=".".join(map(str, parsed)), tag=release["tag_name"][:100], url=release["html_url"])
    return result


def notice(app, current, policy=POLICY, now=None, lang=None):
    entry = policy.get("apps", {}).get(app)
    installed = version(current)
    if not entry or installed is None:
        return None
    minimum = version(entry.get("minimum"))
    if minimum is None or installed >= minimum or not official_url(entry.get("url"), entry["repo"]):
        return None
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    ends = dt.datetime.fromisoformat(POLICY["ends_at"].replace("Z", "+00:00"))
    phase = "after" if now >= ends else "before"
    tr = texts(lang)
    variables = dict(app=entry["name"], current=current, minimum=entry["minimum"], latest=entry.get("tag") or entry["minimum"])
    return dict(title=tr[phase], body="\n\n".join([tr["body_" + phase].format(**variables), tr["risk"], tr["versions"].format(**variables)]),
                url=entry["url"], phase=phase, texts=tr, table=POLICY["table"])


def check(app, current):
    # Unknown/private apps without a public release are never sent to the public API.
    if app not in POLICY["apps"]:
        return None
    policy = copy.deepcopy(POLICY)
    try:
        policy = checked_policy(read_json(POLICY_URL))
    except (OSError, ValueError, TypeError):
        pass
    try:
        repo = POLICY["apps"][app]["repo"]
        policy = with_releases(policy, app, read_json(f"https://api.github.com/repos/Chimpi-hackintosh/{repo}/releases?per_page=30"))
    except (OSError, ValueError, TypeError):
        pass
    return notice(app, current, policy)


def enabled():
    return (os.environ.get("CHIMPI_SUPPORT_CHECK", "1") != "0" and
            not any(arg.startswith(("--gui-smoke", "--smoke-test", "--self-test")) for arg in sys.argv[1:]))


def worker(app, current):
    results = queue.Queue()
    def run():
        try:
            results.put(check(app, current))
        except Exception:
            results.put(None)  # A failed optional check must never prevent startup.
    threading.Thread(target=run, name="Chimpi-support", daemon=True).start()
    return results


def attach_tk(root, app, current):
    if not enabled():
        return
    results = worker(app, current)
    def poll():
        if not root.winfo_exists():
            return
        try:
            item = results.get_nowait()
        except queue.Empty:
            root.after(250, poll)
            return
        if item is None:
            return
        import tkinter as tk
        from tkinter import ttk
        window = tk.Toplevel(root)
        window.title(item["title"])
        window.transient(root)
        window.resizable(False, False)
        window.columnconfigure(0, weight=1)
        ttk.Label(window, text=item["title"], font=("TkDefaultFont", 13, "bold"), wraplength=500).grid(row=0, column=0, padx=22, pady=(20, 12), sticky="w")
        ttk.Label(window, text=item["body"], wraplength=500, justify="left").grid(row=1, column=0, padx=22, pady=8, sticky="w")
        buttons = ttk.Frame(window)
        buttons.grid(row=2, column=0, padx=22, pady=20, sticky="e")
        ttk.Button(buttons, text=item["texts"]["table"], command=lambda: webbrowser.open(item["table"])).pack(side="left", padx=4)
        ttk.Button(buttons, text=item["texts"]["later"], command=window.destroy).pack(side="left", padx=4)
        ttk.Button(buttons, text=item["texts"]["update"], command=lambda: webbrowser.open(item["url"])).pack(side="left", padx=4)
    root.after(800, poll)


def attach_qt(parent, app, current):
    if not enabled():
        return
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QMessageBox
    results = worker(app, current)
    timer = QTimer(parent)
    def poll():
        try:
            item = results.get_nowait()
        except queue.Empty:
            return
        timer.stop()
        if item:
            box = QMessageBox(parent)
            box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            box.setWindowTitle(item["title"])
            box.setTextFormat(Qt.TextFormat.PlainText)
            box.setText(item["title"])
            box.setInformativeText(item["body"])
            update = box.addButton(item["texts"]["update"], QMessageBox.ButtonRole.AcceptRole)
            table = box.addButton(item["texts"]["table"], QMessageBox.ButtonRole.ActionRole)
            box.addButton(item["texts"]["later"], QMessageBox.ButtonRole.RejectRole)
            box.buttonClicked.connect(lambda button: webbrowser.open(item["url"] if button == update else item["table"]) if button in (update, table) else None)
            # Keep the modeless dialog alive until it closes.
            parent._support_notice = box
            box.show()
    timer.timeout.connect(poll)
    timer.start(250)
    parent._support_timer = timer


def attach_gtk(parent, app, current, finished=None):
    if not enabled():
        if finished:
            finished()
        return
    from gi.repository import GLib, Gtk
    results = worker(app, current)
    def poll():
        try:
            item = results.get_nowait()
        except queue.Empty:
            return True
        if item:
            dialog = Gtk.MessageDialog(transient_for=parent, modal=False, message_type=Gtk.MessageType.WARNING, text=item["title"])
            dialog.format_secondary_text(item["body"])
            dialog.add_button(item["texts"]["table"], 1)
            dialog.add_button(item["texts"]["update"], 2)
            dialog.add_button(item["texts"]["later"], Gtk.ResponseType.CLOSE)
            def response(window, value):
                if value in (1, 2):
                    webbrowser.open(item["table"] if value == 1 else item["url"])
                window.destroy()
                if finished:
                    finished()
            dialog.connect("response", response)
            dialog.show_all()
        elif finished:
            finished()
        return False
    GLib.timeout_add(250, poll)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True, choices=sorted(POLICY["apps"]))
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    if not enabled():
        sys.exit(0)
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    attach_gtk(None, args.app, args.version, finished=Gtk.main_quit)
    Gtk.main()
