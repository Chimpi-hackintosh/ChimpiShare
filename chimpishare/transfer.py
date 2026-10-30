"""Small authenticated HTTPS relay. This is the LAN hop, not an AWDL driver."""

import hashlib
import hmac
import http.client
import ipaddress
import json
import os
import re
import secrets
import shutil
import socket
import ssl
import stat
import tempfile
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__
from .errors import ShareError
from .security import Invitation, new_token, safe_filename, server_identity

CHUNK = 256 * 1024
APPROVAL_SECONDS = 90
UPLOAD_SECONDS = 120
MAX_JSON = 8192


def local_ipv4_addresses():
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
    except OSError:
        addresses = set()
    return sorted(a for a in addresses if not ipaddress.ip_address(a).is_loopback) + ["127.0.0.1"]


@dataclass
class Offer:
    identifier: str
    name: str
    size: int
    digest: str
    peer: str
    expires: float
    state: str = "approving"


class _HTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = True

    def __init__(self, address, owner):
        self.owner = owner
        self.slots = threading.BoundedSemaphore(6)
        super().__init__(address, _Handler)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        connection = request
        try:
            # TLS handshake occurs in a bounded worker, not in the accept loop.
            request.settimeout(5)
            connection = self.owner.context.wrap_socket(request, server_side=True)
            connection.settimeout(30)
            self.finish_request(connection, address)
        except (OSError, ValueError):
            pass
        finally:
            self.shutdown_request(connection)
            self.slots.release()

    def handle_error(self, request, address):
        # Never dump invitation tokens or file contents in an HTTP access log.
        pass


class _Handler(BaseHTTPRequestHandler):
    server_version = "ChimpiShare/" + __version__
    sys_version = ""
    protocol_version = "HTTP/1.0"

    @property
    def owner(self):
        return self.server.owner

    def log_message(self, *args):
        pass

    def reply(self, status, data):
        body = json.dumps(data, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def authorized(self):
        headers = self.headers.get_all("Authorization", [])
        expected = "Bearer " + self.owner.token
        if (self.owner.closed.is_set() or len(headers) != 1
                or not hmac.compare_digest(headers[0].encode("utf-8"), expected.encode("ascii"))):
            self.reply(401, {"error": "unauthorized"})
            return False
        return True

    def length(self, maximum):
        values = self.headers.get_all("Content-Length", [])
        if (self.headers.get_all("Transfer-Encoding") or len(values) != 1
                or not re.fullmatch(r"[0-9]{1,12}", values[0])):
            raise ShareError("invalid_request")
        result = int(values[0])
        if result > maximum:
            raise ShareError("too_large")
        return result

    def do_GET(self):
        if not self.authorized():
            return
        if self.path != "/v1/info":
            self.reply(404, {"error": "invalid_request"})
            return
        self.reply(200, {"app": "ChimpiShare", "version": __version__,
                         "max_bytes": self.owner.max_bytes})

    def do_POST(self):
        if not self.authorized():
            return
        if self.path != "/v1/offers":
            self.reply(404, {"error": "invalid_request"})
            return
        try:
            size = self.length(MAX_JSON)
            body = self.rfile.read(size)
            if len(body) != size:
                raise ShareError("interrupted")
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ShareError("invalid_request")
            name = safe_filename(data.get("name"))
            file_size = data.get("size")
            digest = data.get("sha256")
            if (type(file_size) is not int or file_size < 0 or not isinstance(digest, str)
                    or not re.fullmatch(r"[a-f0-9]{64}", digest)):
                raise ShareError("invalid_request")
            if file_size > self.owner.max_bytes:
                raise ShareError("too_large")
            if shutil.disk_usage(self.owner.folder).free < file_size + 1024 * 1024:
                raise ShareError("disk_full")
            offer = Offer(secrets.token_urlsafe(24), name, file_size, digest,
                          self.client_address[0], time.monotonic() + APPROVAL_SECONDS)
            with self.owner.lock:
                previous = self.owner.offer
                if previous and not (previous.state == "ready" and previous.expires < time.monotonic()):
                    raise ShareError("busy")
                self.owner.offer = offer
            try:
                accepted = self.owner.approve(offer)
            except Exception:
                accepted = False
            with self.owner.lock:
                if not accepted or self.owner.closed.is_set() or offer.expires < time.monotonic():
                    if self.owner.offer is offer:
                        self.owner.offer = None
                    raise ShareError("denied")
                offer.state = "ready"
                offer.expires = time.monotonic() + UPLOAD_SECONDS
            self.reply(201, {"id": offer.identifier, "name": name})
        except ShareError as exc:
            status = {"denied": 403, "busy": 409, "too_large": 413, "disk_full": 507}.get(exc.code, 400)
            self.reply(status, {"error": exc.code})
        except (ValueError, UnicodeError, OSError, RecursionError):
            self.reply(400, {"error": "invalid_request"})

    def do_PUT(self):
        if not self.authorized():
            return
        offer = None
        temp_dir = None
        try:
            with self.owner.lock:
                pending = self.owner.offer
                if (not pending or pending.state != "ready" or pending.expires < time.monotonic()
                        or self.path != "/v1/files/" + pending.identifier
                        or self.client_address[0] != pending.peer):
                    raise ShareError("expired")
                pending.state = "uploading"
                offer = pending
            if self.length(self.owner.max_bytes) != offer.size:
                raise ShareError("invalid_request")
            temp_dir = Path(tempfile.mkdtemp(prefix=".incoming-", dir=self.owner.folder))
            partial = temp_dir / "payload.part"
            digest, remaining = hashlib.sha256(), offer.size
            with partial.open("xb") as output:
                while remaining:
                    if self.owner.closed.is_set():
                        raise ShareError("interrupted")
                    block = self.rfile.read(min(CHUNK, remaining))
                    if not block:
                        raise ShareError("interrupted")
                    output.write(block)
                    digest.update(block)
                    remaining -= len(block)
                output.flush()
                os.fsync(output.fileno())
            if not hmac.compare_digest(digest.hexdigest(), offer.digest):
                raise ShareError("checksum_mismatch")
            if self.owner.closed.is_set():
                raise ShareError("interrupted")
            final_name = temp_dir / offer.name
            os.replace(partial, final_name)
            # Publish a complete, uniquely named directory, preserving duplicate basenames.
            published = self.owner.folder / ("received-" + temp_dir.name[len(".incoming-"):])
            os.rename(temp_dir, published)
            temp_dir = None
            saved = published / offer.name
            self.owner.notify("received", path=str(saved), name=offer.name, size=offer.size)
            self.reply(201, {"name": offer.name, "size": offer.size, "sha256": offer.digest})
        except ShareError as exc:
            self.reply(410 if exc.code == "expired" else 400, {"error": exc.code})
        except OSError:
            self.reply(500, {"error": "storage_error"})
        finally:
            if temp_dir is not None:
                shutil.rmtree(temp_dir, ignore_errors=True)
            if offer is not None:
                with self.owner.lock:
                    if self.owner.offer is offer:
                        self.owner.offer = None


class Receiver:
    def __init__(self, folder, approve, notify=None, host="0.0.0.0", port=48765,
                 max_bytes=2048 * 1024 * 1024):
        self.folder = Path(folder).expanduser().resolve()
        self.folder.mkdir(parents=True, exist_ok=True)
        self.approve = approve
        self.notify = notify or (lambda *args, **kwargs: None)
        self.max_bytes = max_bytes
        self.token = new_token()
        self.closed = threading.Event()
        self.lock = threading.Lock()
        self.offer = None
        self.thread = None
        self.identity_dir = tempfile.TemporaryDirectory(prefix="chimpishare-tls-")
        try:
            self.context, self.fingerprint = server_identity(self.identity_dir.name)
            self.http = _HTTPServer((host, port), self)
        except BaseException:
            self.identity_dir.cleanup()
            raise
        self.port = self.http.server_address[1]

    def start(self):
        if self.thread is not None:
            raise RuntimeError("Receiver already started")
        self.thread = threading.Thread(target=self.http.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
        self.thread.start()
        return self

    def invitation(self, host):
        invitation = Invitation(str(host), self.port, self.token, self.fingerprint)
        return Invitation.parse(invitation.encode()).encode()

    def close(self):
        if self.closed.is_set():
            return
        self.closed.set()
        if self.thread is not None:
            self.http.shutdown()
            self.thread.join(timeout=2)
        self.http.server_close()
        self.identity_dir.cleanup()


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, invitation, timeout=APPROVAL_SECONDS + 15):
        self.invitation = invitation
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        # Identity is verified by the invitation's certificate fingerprint, not a public CA.
        # No HTTP headers, credentials or file data are sent before the pin matches.
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        super().__init__(invitation.host, invitation.port, timeout=timeout, context=context)

    def connect(self):
        super().connect()
        actual = hashlib.sha256(self.sock.getpeercert(binary_form=True)).hexdigest()
        if not hmac.compare_digest(actual, self.invitation.fingerprint):
            self.close()
            raise ShareError("certificate_mismatch")


def _read_response(connection):
    response = connection.getresponse()
    body = response.read(MAX_JSON + 1)
    if len(body) > MAX_JSON:
        raise ShareError("invalid_response")
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError, RecursionError):
        raise ShareError("invalid_response") from None
    if not isinstance(data, dict):
        raise ShareError("invalid_response")
    if response.status >= 400:
        known = {"unauthorized", "denied", "busy", "too_large", "disk_full", "expired",
                 "invalid_request", "checksum_mismatch", "storage_error", "interrupted", "invalid_filename"}
        code = data.get("error")
        raise ShareError(code if code in known else "invalid_response")
    if response.status not in {200, 201}:
        raise ShareError("invalid_response")
    return data


def _request(invitation, method, path, data=None):
    conn = PinnedHTTPSConnection(invitation)
    body = json.dumps(data).encode("utf-8") if data is not None else None
    try:
        conn.connect()
        conn.request(method, path, body=body,
                     headers={"Authorization": "Bearer " + invitation.token,
                              "Content-Type": "application/json"})
        return _read_response(conn)
    finally:
        conn.close()


def inspect_receiver(invitation_text):
    return _request(Invitation.parse(invitation_text), "GET", "/v1/info")


def send_file(invitation_text, path, progress=None):
    invitation = Invitation.parse(invitation_text)
    path = Path(path).expanduser()
    if path.is_symlink():
        raise ShareError("regular_files_only")
    safe_filename(path.name)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                         | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ShareError("regular_files_only")
        info = _request(invitation, "GET", "/v1/info")
        if (info.get("app") != "ChimpiShare" or type(info.get("max_bytes")) is not int):
            raise ShareError("invalid_response")
        if before.st_size > info["max_bytes"]:
            raise ShareError("too_large")
        digest = hashlib.sha256()
        for block in iter(lambda: source.read(CHUNK), b""):
            digest.update(block)
        after = os.fstat(source.fileno())
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ShareError("file_changed")
        source.seek(0)
        expected_digest = digest.hexdigest()
        offer = _request(invitation, "POST", "/v1/offers",
                         {"name": path.name, "size": before.st_size, "sha256": expected_digest})
        identifier = offer.get("id")
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32}", identifier):
            raise ShareError("invalid_response")
        conn = PinnedHTTPSConnection(invitation, timeout=60)
        try:
            conn.connect()
            conn.putrequest("PUT", "/v1/files/" + identifier)
            conn.putheader("Authorization", "Bearer " + invitation.token)
            conn.putheader("Content-Type", "application/octet-stream")
            conn.putheader("Content-Length", str(before.st_size))
            conn.endheaders()
            sent = 0
            while sent < before.st_size:
                block = source.read(min(CHUNK, before.st_size - sent))
                if not block:
                    raise ShareError("file_changed")
                conn.send(block)
                sent += len(block)
                if progress:
                    progress(sent, before.st_size)
            result = _read_response(conn)
            if result.get("sha256") != expected_digest or result.get("size") != before.st_size:
                raise ShareError("invalid_response")
            if progress:
                progress(before.st_size, before.st_size)
            return result
        finally:
            conn.close()
