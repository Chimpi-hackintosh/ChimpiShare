import base64
import dataclasses
import hashlib
import os
import socket
import tempfile
import time
import unittest
from pathlib import Path

from chimpishare.errors import ShareError
from chimpishare.security import Invitation, new_token
from chimpishare.transfer import (PinnedHTTPSConnection, Receiver, _read_response,
                                 _request, inspect_receiver, send_file)


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.received = self.root / "received"
        self.allowed = True
        self.offers = []
        self.events = []

        def approve(offer):
            self.offers.append(offer)
            return self.allowed

        self.receiver = Receiver(self.received, approve, lambda *args, **kw: self.events.append((args, kw)),
                                 host="127.0.0.1", port=0, max_bytes=2 * 1024 * 1024).start()
        self.invitation_text = self.receiver.invitation("127.0.0.1")
        self.invitation = Invitation.parse(self.invitation_text)

    def tearDown(self):
        self.receiver.close()
        self.temp.cleanup()

    def source(self, name="Arquivo.png", data=b"test content"):
        folder = self.root / "source"
        folder.mkdir(exist_ok=True)
        path = folder / name
        path.write_bytes(data)
        return path

    def saved(self):
        return sorted(self.received.glob("received-*/*"))

    def assert_error(self, expected, call):
        with self.assertRaises(ShareError) as error:
            call()
        self.assertEqual(error.exception.code, expected)

    def offer(self, data=b"hello", name="file.bin", digest=None):
        return _request(self.invitation, "POST", "/v1/offers",
                        {"name": name, "size": len(data),
                         "sha256": digest or hashlib.sha256(data).hexdigest()})

    def upload(self, identifier, data, declared_size=None):
        connection = PinnedHTTPSConnection(self.invitation)
        try:
            connection.connect()
            connection.request("PUT", "/v1/files/" + identifier, body=data,
                               headers={"Authorization": "Bearer " + self.invitation.token,
                                        "Content-Length": str(len(data) if declared_size is None else declared_size)})
            return _read_response(connection)
        finally:
            connection.close()

    def test_png_bytes_survive_transfer(self):
        data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aFOsAAAAASUVORK5CYII=")
        result = send_file(self.invitation_text, self.source(data=data))
        self.assertEqual(self.saved()[0].read_bytes(), data)
        self.assertEqual(result["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(len(self.events), 1)

    def test_multi_chunk_binary_and_progress(self):
        data = os.urandom(1024 * 1024 + 19)
        progress = []
        send_file(self.invitation_text, self.source(data=data), lambda a, b: progress.append((a, b)))
        self.assertEqual(self.saved()[0].read_bytes(), data)
        self.assertEqual(progress[-1], (len(data), len(data)))
        self.assertGreater(len(progress), 2)

    def test_empty_file(self):
        send_file(self.invitation_text, self.source(data=b""))
        self.assertEqual(self.saved()[0].read_bytes(), b"")

    def test_unicode_filename(self):
        path = self.source(name="Olá 🦧.txt", data="Olá chefinho".encode())
        send_file(self.invitation_text, path)
        self.assertEqual(self.saved()[0].name, path.name)
        self.assertEqual(self.saved()[0].read_bytes(), path.read_bytes())

    def test_same_filename_never_overwrites(self):
        path = self.source(data=b"first")
        send_file(self.invitation_text, path)
        path.write_bytes(b"second")
        send_file(self.invitation_text, path)
        self.assertEqual({p.read_bytes() for p in self.saved()}, {b"first", b"second"})
        self.assertEqual(len(self.saved()), 2)

    def test_recipient_can_decline(self):
        self.allowed = False
        self.assert_error("denied", lambda: send_file(self.invitation_text, self.source()))
        self.assertEqual(self.saved(), [])
        self.assertIsNone(self.receiver.offer)

    def test_wrong_session_token_rejected_before_approval(self):
        wrong = dataclasses.replace(self.invitation, token=new_token()).encode()
        self.assert_error("unauthorized", lambda: send_file(wrong, self.source()))
        self.assertEqual(self.offers, [])

    def test_wrong_certificate_pin_rejected(self):
        wrong = dataclasses.replace(self.invitation, fingerprint="0" * 64).encode()
        self.assert_error("certificate_mismatch", lambda: send_file(wrong, self.source()))
        self.assertEqual(self.offers, [])
        self.assertEqual(self.saved(), [])

    def test_corrupt_payload_not_published(self):
        offer = self.offer(b"original")
        self.assert_error("checksum_mismatch", lambda: self.upload(offer["id"], b"tampered"))
        self.assertEqual(self.saved(), [])
        self.assertEqual(list(self.received.iterdir()), [])

    def test_path_traversal_rejected(self):
        self.assert_error("invalid_filename", lambda: self.offer(name="../escape.txt"))
        self.assertEqual(self.offers, [])

    def test_windows_reserved_name_sanitized(self):
        data = b"test"
        offer = self.offer(data, name="CON.txt")
        result = self.upload(offer["id"], data)
        self.assertEqual(result["name"], "_CON.txt")
        self.assertEqual(self.saved()[0].name, "_CON.txt")

    def test_oversized_file_rejected_before_approval(self):
        self.receiver.max_bytes = 3
        self.assert_error("too_large", lambda: send_file(self.invitation_text, self.source(data=b"1234")))
        self.assertEqual(self.offers, [])

    def test_offer_size_limit_applies_to_other_clients(self):
        self.receiver.max_bytes = 3
        self.assert_error("too_large", lambda: self.offer(b"1234"))
        self.assertEqual(self.offers, [])

    def test_expired_authorization_rejected(self):
        offer = self.offer()
        self.receiver.offer.expires = time.monotonic() - 1
        self.assert_error("expired", lambda: self.upload(offer["id"], b"hello"))
        self.assertEqual(self.saved(), [])

    def test_upload_authorization_is_single_use(self):
        offer = self.offer()
        self.upload(offer["id"], b"hello")
        self.assert_error("expired", lambda: self.upload(offer["id"], b"hello"))
        self.assertEqual(len(self.saved()), 1)

    def test_mismatched_length_rejected(self):
        offer = self.offer(b"123456")
        self.assert_error("invalid_request", lambda: self.upload(offer["id"], b"12345"))
        self.assertEqual(list(self.received.iterdir()), [])

    def test_interrupted_upload_cleans_partial_file(self):
        offer = self.offer(b"x" * 1024)
        connection = PinnedHTTPSConnection(self.invitation)
        connection.connect()
        connection.putrequest("PUT", "/v1/files/" + offer["id"])
        connection.putheader("Authorization", "Bearer " + self.invitation.token)
        connection.putheader("Content-Length", "1024")
        connection.endheaders()
        connection.send(b"x" * 10)
        deadline = time.monotonic() + 2
        while not list(self.received.glob(".incoming-*")) and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(list(self.received.glob(".incoming-*")))
        connection.close()
        deadline = time.monotonic() + 2
        while self.receiver.offer is not None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertIsNone(self.receiver.offer)
        self.assertEqual(list(self.received.iterdir()), [])

    def test_another_offer_is_busy_until_first_expires(self):
        self.offer()
        self.assert_error("busy", lambda: self.offer())
        self.receiver.offer.expires = time.monotonic() - 1
        self.offer()
        self.assertEqual(len(self.offers), 2)

    def test_stalled_tls_handshake_does_not_block_other_client(self):
        stalled = socket.create_connection(("127.0.0.1", self.receiver.port), timeout=2)
        try:
            started = time.monotonic()
            info = inspect_receiver(self.invitation_text)
            self.assertEqual(info["app"], "ChimpiShare")
            self.assertLess(time.monotonic() - started, 3)
        finally:
            stalled.close()

    def test_repeated_content_length_rejected(self):
        connection = PinnedHTTPSConnection(self.invitation)
        try:
            connection.connect()
            connection.putrequest("POST", "/v1/offers")
            connection.putheader("Authorization", "Bearer " + self.invitation.token)
            connection.putheader("Content-Length", "2")
            connection.putheader("Content-Length", "9")
            connection.endheaders()
            self.assert_error("invalid_request", lambda: _read_response(connection))
        finally:
            connection.close()
        self.assertEqual(self.offers, [])

    def test_chunked_request_rejected(self):
        connection = PinnedHTTPSConnection(self.invitation)
        try:
            connection.connect()
            connection.putrequest("POST", "/v1/offers")
            connection.putheader("Authorization", "Bearer " + self.invitation.token)
            connection.putheader("Content-Length", "2")
            connection.putheader("Transfer-Encoding", "chunked")
            connection.endheaders()
            self.assert_error("invalid_request", lambda: _read_response(connection))
        finally:
            connection.close()

    def test_symlink_not_sent(self):
        target = self.source()
        link = target.parent / "link.png"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable on this host")
        self.assert_error("regular_files_only", lambda: send_file(self.invitation_text, link))
        self.assertEqual(self.offers, [])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX named pipe test")
    def test_named_pipe_rejected_without_waiting_for_a_writer(self):
        folder = self.root / "source"
        folder.mkdir()
        pipe = folder / "pipe"
        os.mkfifo(pipe)
        started = time.monotonic()
        self.assert_error("regular_files_only", lambda: send_file(self.invitation_text, pipe))
        self.assertLess(time.monotonic() - started, 1)
        self.assertEqual(self.offers, [])

    def test_new_session_has_new_invitation(self):
        original = self.invitation
        self.receiver.close()
        self.receiver = Receiver(self.received, lambda offer: True, host="127.0.0.1", port=0).start()
        fresh = Invitation.parse(self.receiver.invitation("127.0.0.1"))
        self.assertNotEqual(original.token, fresh.token)
        self.assertNotEqual(original.fingerprint, fresh.fingerprint)


if __name__ == "__main__":
    unittest.main()
