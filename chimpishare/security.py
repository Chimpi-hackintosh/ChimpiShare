import hashlib
import ipaddress
import re
import secrets
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from .errors import ShareError


@dataclass(frozen=True)
class Invitation:
    host: str
    port: int
    token: str = field(repr=False)
    fingerprint: str = field(repr=False)

    def encode(self):
        return f"chimpishare://{self.host}:{self.port}/v1#{self.token}:{self.fingerprint}"

    @classmethod
    def parse(cls, text):
        try:
            url = urlsplit(text.strip())
            token, fingerprint = url.fragment.split(":")
            host, port = str(ipaddress.IPv4Address(url.hostname)), url.port
            address = ipaddress.IPv4Address(host)
            if (url.scheme != "chimpishare" or url.path != "/v1" or url.query
                    or url.username or url.password or port is None or not 1 <= port <= 65535
                    or address.is_unspecified or address.is_multicast or str(address) == "255.255.255.255"
                    or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token)
                    or not re.fullmatch(r"[a-f0-9]{64}", fingerprint)):
                raise ValueError
            return cls(host, port, token, fingerprint)
        except (ValueError, TypeError, AttributeError):
            raise ShareError("invalid_invitation") from None


def new_token():
    return secrets.token_urlsafe(32)


def server_identity(folder):
    """New self-signed identity for each listening session; never shipped in a build."""
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ChimpiShare local session")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=2))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    key_path, cert_path = Path(folder) / "key.pem", Path(folder) / "cert.pem"
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                         serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
    key_path.chmod(0o600)
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert_path, key_path)
    return context, hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()


def safe_filename(name):
    if (not isinstance(name, str) or not name or name in {".", ".."}
            or "/" in name or "\\" in name or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        raise ShareError("invalid_filename")
    try:
        if len(name.encode("utf-8")) > 220:
            raise ShareError("invalid_filename")
    except UnicodeError:
        raise ShareError("invalid_filename") from None
    cleaned = re.sub(r'[<>:"|?*]', "_", name).rstrip(". ")
    if not cleaned or cleaned.startswith("."):
        cleaned = "_" + cleaned.lstrip(".")
    stem = cleaned.split(".")[0].upper()
    if stem in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}:
        cleaned = "_" + cleaned
    return cleaned
