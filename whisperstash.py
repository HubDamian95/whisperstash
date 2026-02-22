#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import re
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

VERSION = b"NC1"
SALT_LEN = 16
NONCE_LEN = 12
PBKDF2_ITERS = 250_000
WRAP_RE = re.compile(r"ENC\[([A-Za-z0-9_\-=]+)\]")


def derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERS,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_text(passphrase: str, plaintext: str) -> str:
    salt = os.urandom(SALT_LEN)
    nonce = os.urandom(NONCE_LEN)
    key = derive_key(passphrase, salt)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    token = VERSION + salt + nonce + ciphertext
    return base64.urlsafe_b64encode(token).decode("ascii")


def decrypt_text(passphrase: str, token: str) -> str:
    raw = base64.urlsafe_b64decode(token.encode("ascii"))
    if len(raw) < len(VERSION) + SALT_LEN + NONCE_LEN + 16:
        raise ValueError("Token is too short or malformed.")
    if raw[: len(VERSION)] != VERSION:
        raise ValueError("Unsupported token version.")
    pos = len(VERSION)
    salt = raw[pos : pos + SALT_LEN]
    pos += SALT_LEN
    nonce = raw[pos : pos + NONCE_LEN]
    pos += NONCE_LEN
    ciphertext = raw[pos:]
    key = derive_key(passphrase, salt)
    plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def read_key(cli_key: str | None) -> str:
    if cli_key is not None:
        if not cli_key:
            raise ValueError("Empty key is not allowed.")
        return cli_key
    key = getpass.getpass("Enter key/passphrase: ")
    if not key:
        raise ValueError("Empty key is not allowed.")
    return key


def wrap_text(passphrase: str, plaintext: str) -> str:
    return f"ENC[{encrypt_text(passphrase, plaintext)}]"


def unwrap_text(passphrase: str, text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        token = match.group(1)
        return decrypt_text(passphrase, token)

    return WRAP_RE.sub(repl, text)


def cmd_encrypt(args: argparse.Namespace) -> int:
    key = read_key(args.key)
    text = args.text if args.text is not None else _read_file_text(args.in_file)
    print(encrypt_text(key, text))
    return 0


def cmd_decrypt(args: argparse.Namespace) -> int:
    key = read_key(args.key)
    token = args.token if args.token is not None else _read_file_text(args.in_file).strip()
    print(decrypt_text(key, token))
    return 0


def cmd_wrap(args: argparse.Namespace) -> int:
    key = read_key(args.key)
    text = args.text if args.text is not None else _read_file_text(args.in_file)
    print(wrap_text(key, text))
    return 0


def cmd_unwrap(args: argparse.Namespace) -> int:
    key = read_key(args.key)
    text = args.text if args.text is not None else _read_file_text(args.in_file)
    print(unwrap_text(key, text))
    return 0


def cmd_view(args: argparse.Namespace) -> int:
    key = read_key(args.key)
    token = _read_file_text(args.file).strip()
    plain = decrypt_text(key, token)
    pager = os.environ.get("PAGER", "less")
    proc = subprocess.run([pager], input=plain.encode("utf-8"), check=False)
    return proc.returncode


def cmd_edit(args: argparse.Namespace) -> int:
    key = read_key(args.key)
    token = _read_file_text(args.file).strip()
    plain = decrypt_text(key, token)

    editor = os.environ.get("EDITOR", "nano")
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt", encoding="utf-8") as tf:
        temp_path = tf.name
        tf.write(plain)

    try:
        subprocess.run([editor, temp_path], check=True)
        updated = _read_file_text(temp_path)
        new_token = encrypt_text(key, updated)
        _write_file_text(args.file, new_token + "\n")
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass
    return 0


def cmd_server(args: argparse.Namespace) -> int:
    key = read_key(args.key)

    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            origin = self.headers.get("Origin", "")
            if origin.startswith("chrome-extension://") or origin in {"http://localhost", "http://127.0.0.1"}:
                self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            self._send_json(200, {"ok": True})

        def do_GET(self) -> None:
            if self.path == "/health":
                self._send_json(200, {"ok": True, "service": "whisperstash", "version": "1"})
                return
            self._send_json(404, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._send_json(400, {"ok": False, "error": "invalid json"})
                return

            try:
                if self.path == "/encrypt":
                    text = str(data.get("text", ""))
                    token = encrypt_text(key, text)
                    self._send_json(200, {"ok": True, "token": token, "wrapped": f"ENC[{token}]"})
                    return
                if self.path == "/decrypt":
                    token = str(data.get("token", ""))
                    plain = decrypt_text(key, token)
                    self._send_json(200, {"ok": True, "text": plain})
                    return
                if self.path == "/unwrap":
                    text = str(data.get("text", ""))
                    plain = unwrap_text(key, text)
                    self._send_json(200, {"ok": True, "text": plain})
                    return
            except Exception as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
                return

            self._send_json(404, {"ok": False, "error": "not found"})

        def log_message(self, fmt: str, *args) -> None:
            if not args:
                return

    server = HTTPServer((args.host, args.port), Handler)
    print(f"whisperstash server listening on http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()
    return 0


def _read_file_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_file_text(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="All-in-one encrypted text toolkit for CLI + browser extension.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("encrypt", help="Encrypt text to token")
    p.add_argument("--text", help="Plain text")
    p.add_argument("--in-file", help="Read plain text from file")
    p.add_argument("--key", help="Passphrase (avoid shell history)")
    p.set_defaults(func=cmd_encrypt)

    p = sub.add_parser("decrypt", help="Decrypt token to plain text")
    p.add_argument("--token", help="Encrypted token")
    p.add_argument("--in-file", help="Read token from file")
    p.add_argument("--key", help="Passphrase (avoid shell history)")
    p.set_defaults(func=cmd_decrypt)

    p = sub.add_parser("wrap", help="Encrypt and wrap as ENC[...] ")
    p.add_argument("--text", help="Plain text")
    p.add_argument("--in-file", help="Read plain text from file")
    p.add_argument("--key", help="Passphrase (avoid shell history)")
    p.set_defaults(func=cmd_wrap)

    p = sub.add_parser("unwrap", help="Decrypt all ENC[...] blocks in text")
    p.add_argument("--text", help="Input text containing ENC[...] blocks")
    p.add_argument("--in-file", help="Read input from file")
    p.add_argument("--key", help="Passphrase (avoid shell history)")
    p.set_defaults(func=cmd_unwrap)

    p = sub.add_parser("view", help="Decrypt token file and view in pager")
    p.add_argument("file", help="File containing a token")
    p.add_argument("--key", help="Passphrase (avoid shell history)")
    p.set_defaults(func=cmd_view)

    p = sub.add_parser("edit", help="Decrypt token file, edit, and re-encrypt")
    p.add_argument("file", help="File containing a token")
    p.add_argument("--key", help="Passphrase (avoid shell history)")
    p.set_defaults(func=cmd_edit)

    p = sub.add_parser("server", help="Run localhost API for browser extension")
    p.add_argument("--host", default="127.0.0.1", help="Host bind address")
    p.add_argument("--port", type=int, default=8765, help="Port")
    p.add_argument("--key", help="Passphrase (avoid shell history)")
    p.set_defaults(func=cmd_server)

    return parser


def _validate_source_args(args: argparse.Namespace) -> None:
    if getattr(args, "text", None) is None and getattr(args, "in_file", None) is None:
        raise ValueError("Provide --text or --in-file")
    if getattr(args, "text", None) is not None and getattr(args, "in_file", None) is not None:
        raise ValueError("Use only one of --text or --in-file")
    if getattr(args, "token", None) is None and getattr(args, "in_file", None) is None:
        raise ValueError("Provide --token or --in-file")
    if getattr(args, "token", None) is not None and getattr(args, "in_file", None) is not None:
        raise ValueError("Use only one of --token or --in-file")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command in {"encrypt", "wrap"}:
            if args.text is None and args.in_file is None:
                raise ValueError("Provide --text or --in-file")
            if args.text is not None and args.in_file is not None:
                raise ValueError("Use only one of --text or --in-file")
        if args.command in {"decrypt"}:
            if args.token is None and args.in_file is None:
                raise ValueError("Provide --token or --in-file")
            if args.token is not None and args.in_file is not None:
                raise ValueError("Use only one of --token or --in-file")
        if args.command in {"unwrap"}:
            if args.text is None and args.in_file is None:
                raise ValueError("Provide --text or --in-file")
            if args.text is not None and args.in_file is not None:
                raise ValueError("Use only one of --text or --in-file")

        return args.func(args)
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
