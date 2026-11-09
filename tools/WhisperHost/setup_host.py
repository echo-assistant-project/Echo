"""One-time setup for the Echo Whisper host (run with the host's venv Python).

Creates, outside the repository, in --home:  cert.pem / key.pem (self-signed, localhost), pairing.json
({endpoint, key, fingerprint, model}) and downloads the model into models/. Never prints the key.
"""
import argparse
import datetime
import hashlib
import ipaddress
import json
import secrets
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def make_cert(home: Path) -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Echo Whisper host (localhost)")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
            .sign(key, hashes.SHA256()))
    (home / "key.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    der = cert.public_bytes(serialization.Encoding.DER)
    (home / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return hashlib.sha256(der).hexdigest().upper()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", required=True)
    ap.add_argument("--model", default="small.en")
    ap.add_argument("--port", type=int, default=31417)
    args = ap.parse_args()
    home = Path(args.home)
    home.mkdir(parents=True, exist_ok=True)
    pairing = home / "pairing.json"
    if pairing.exists():
        data = json.loads(pairing.read_text(encoding="utf-8"))
        data["model"] = args.model
    else:
        data = {"endpoint": f"https://127.0.0.1:{args.port}/v1/stt", "key": secrets.token_urlsafe(32),
                "fingerprint": make_cert(home), "model": args.model}
    pairing.write_text(json.dumps(data, indent=1), encoding="utf-8")
    from faster_whisper import WhisperModel
    WhisperModel(args.model, device="cpu", compute_type="int8", download_root=str(home / "models"))
    print(f"Ready: model {args.model}; endpoint {data['endpoint']}; certificate SHA-256 {data['fingerprint']}")
    print(f"Pairing details (keep private): {pairing}")


if __name__ == "__main__":
    main()
