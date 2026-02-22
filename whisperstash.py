#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
import getpass
import hmac
import json
import os
import stat
import re
import subprocess
import sys
import tempfile
import ctypes
import hashlib
import fnmatch
import urllib.request
import urllib.error
import shlex
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

VERSION = b"NC1"
VERSION_INTEGRITY = b"NC2"
SALT_LEN = 16
NONCE_LEN = 12
PBKDF2_ITERS = 250_000
WRAP_RE = re.compile(r"ENC\[([A-Za-z0-9_\-=]+)\]")


def _default_key_path() -> str:
    base_dir = os.environ.get("WHISPERSTASH_HOME")
    if base_dir:
        return os.path.join(base_dir, ".default_key")
    return os.path.expanduser("~/.whisperstash_default_key")


def _read_default_key() -> str | None:
    path = _default_key_path()
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read().strip()
    if not raw:
        return None
    if raw.startswith("DPAPI:"):
        if sys.platform != "win32":
            raise ValueError("DPAPI-protected key file can only be read on Windows.")
        blob_b64 = raw[len("DPAPI:") :]
        try:
            blob = base64.b64decode(blob_b64.encode("ascii"), validate=True)
        except (binascii.Error, UnicodeEncodeError) as exc:
            raise ValueError(f"Corrupt DPAPI key file: {exc}") from exc
        key = _dpapi_unprotect(blob).decode("utf-8")
        return key or None
    key = raw
    return key or None


def _write_default_key(key: str) -> str:
    path = _default_key_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if sys.platform == "win32":
            blob = _dpapi_protect(key.encode("utf-8"))
            f.write(f"DPAPI:{base64.b64encode(blob).decode('ascii')}\n")
        else:
            f.write(key + "\n")
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return path


def _clear_default_key() -> str:
    path = _default_key_path()
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    return path


if sys.platform == "win32":
    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


    def _dpapi_protect(data: bytes) -> bytes:
        in_buf = ctypes.create_string_buffer(data)
        in_blob = _DATA_BLOB(len(data), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_ubyte)))
        out_blob = _DATA_BLOB()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        if not crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob),
        ):
            raise ValueError("Unable to protect key with Windows DPAPI.")
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)


    def _dpapi_unprotect(data: bytes) -> bytes:
        in_buf = ctypes.create_string_buffer(data)
        in_blob = _DATA_BLOB(len(data), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_ubyte)))
        out_blob = _DATA_BLOB()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        if not crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob),
        ):
            raise ValueError("Unable to unprotect key with Windows DPAPI.")
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)


def derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERS,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def derive_integrity_key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt + b"|mac", PBKDF2_ITERS, dklen=32)


def encrypt_text(passphrase: str, plaintext: str, integrity: bool = False) -> str:
    salt = os.urandom(SALT_LEN)
    nonce = os.urandom(NONCE_LEN)
    key = derive_key(passphrase, salt)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    if integrity:
        mac_key = derive_integrity_key(passphrase, salt)
        msg = VERSION_INTEGRITY + salt + nonce + ciphertext
        mac = hmac.new(mac_key, msg, hashlib.sha256).digest()
        token = msg + mac
    else:
        token = VERSION + salt + nonce + ciphertext
    return base64.urlsafe_b64encode(token).decode("ascii")


def decrypt_text(passphrase: str, token: str) -> str:
    raw = base64.urlsafe_b64decode(token.encode("ascii"))
    if len(raw) < len(VERSION) + SALT_LEN + NONCE_LEN + 16:
        raise ValueError("Token is too short or malformed.")
    version = raw[: len(VERSION)]
    if version not in {VERSION, VERSION_INTEGRITY}:
        raise ValueError("Unsupported token version.")
    pos = len(VERSION)
    salt = raw[pos : pos + SALT_LEN]
    pos += SALT_LEN
    nonce = raw[pos : pos + NONCE_LEN]
    pos += NONCE_LEN
    if version == VERSION_INTEGRITY:
        if len(raw) < len(VERSION_INTEGRITY) + SALT_LEN + NONCE_LEN + 16 + 32:
            raise ValueError("Token is too short or malformed.")
        ciphertext = raw[pos:-32]
        mac = raw[-32:]
        mac_key = derive_integrity_key(passphrase, salt)
        expected = hmac.new(mac_key, raw[: len(raw) - 32], hashlib.sha256).digest()
        if not hmac.compare_digest(expected, mac):
            raise ValueError("Integrity check failed (token may be tampered or key is wrong).")
    else:
        ciphertext = raw[pos:]
    key = derive_key(passphrase, salt)
    plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def read_key(cli_key: str | None) -> str:
    if cli_key is not None:
        if not cli_key:
            raise ValueError("Empty key is not allowed.")
        return cli_key
    default_key = _read_default_key()
    if default_key:
        return default_key
    key = getpass.getpass("Enter key/passphrase: ")
    if not key:
        raise ValueError("Empty key is not allowed.")
    return key


def cmd_key_set(args: argparse.Namespace) -> int:
    if args.key is not None:
        key = args.key
    else:
        key = getpass.getpass("Set default key/passphrase: ")
    if not key:
        raise ValueError("Empty key is not allowed.")
    path = _write_default_key(key)
    print(f"Default key saved: {path}")
    return 0


def cmd_key_clear(args: argparse.Namespace) -> int:
    path = _clear_default_key()
    print(f"Default key cleared: {path}")
    return 0


def cmd_key_status(args: argparse.Namespace) -> int:
    path = _default_key_path()
    if _read_default_key() is None:
        print(f"No default key set ({path})")
    else:
        print(f"Default key is set ({path})")
    return 0


def wrap_text(passphrase: str, plaintext: str, integrity: bool = False) -> str:
    return f"ENC[{encrypt_text(passphrase, plaintext, integrity=integrity)}]"


def unwrap_text(passphrase: str, text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        token = match.group(1)
        return decrypt_text(passphrase, token)

    return WRAP_RE.sub(repl, text)


def cmd_encrypt(args: argparse.Namespace) -> int:
    key = read_key(args.key)
    if args.from_clipboard:
        text = _read_clipboard_text()
    else:
        text = args.text if args.text is not None else _read_text_with_prompt(
            args.in_file,
            "Please enter what you'd like to encrypt.",
            multiline=True,
        )
    token = encrypt_text(key, text, integrity=args.integrity)
    print(token)
    if args.copy:
        _write_clipboard_text(token)
        print("Copied result to clipboard.")
    return 0


def cmd_decrypt(args: argparse.Namespace) -> int:
    key = read_key(args.key)
    if args.from_clipboard:
        token = _read_clipboard_text().strip()
    else:
        token = args.token if args.token is not None else _read_text_with_prompt(
            args.in_file,
            "Please enter the token you'd like to decrypt",
        ).strip()
    plain = decrypt_text(key, token)
    print(plain)
    if args.copy:
        _write_clipboard_text(plain)
        print("Copied result to clipboard.")
    return 0


def cmd_wrap(args: argparse.Namespace) -> int:
    key = read_key(args.key)
    if args.from_clipboard:
        text = _read_clipboard_text()
    else:
        text = args.text if args.text is not None else _read_text_with_prompt(
            args.in_file,
            "Please enter what you'd like to wrap.",
            multiline=True,
        )
    wrapped = wrap_text(key, text, integrity=args.integrity)
    print(wrapped)
    if args.copy:
        _write_clipboard_text(wrapped)
        print("Copied result to clipboard.")
    return 0


def cmd_unwrap(args: argparse.Namespace) -> int:
    key = read_key(args.key)
    if args.from_clipboard:
        text = _read_clipboard_text()
    else:
        text = args.text if args.text is not None else _read_text_with_prompt(
            args.in_file,
            "Please enter text containing ENC[...] to unwrap.",
            multiline=True,
        )
    unwrapped = unwrap_text(key, text)
    print(unwrapped)
    if args.copy:
        _write_clipboard_text(unwrapped)
        print("Copied result to clipboard.")
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
        new_token = encrypt_text(key, updated, integrity=args.integrity)
        _write_file_text(args.file, new_token + "\n")
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass
    return 0


def cmd_server(args: argparse.Namespace) -> int:
    key = read_key(args.key)
    auth_token = args.auth_token if args.auth_token else os.environ.get("WHISPERSTASH_AUTH_TOKEN")

    class Handler(BaseHTTPRequestHandler):
        def _is_authorized(self) -> bool:
            if not auth_token:
                return True
            header = self.headers.get("Authorization", "")
            expected = f"Bearer {auth_token}"
            return hmac.compare_digest(header, expected)

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
            if not self._is_authorized():
                self._send_json(401, {"ok": False, "error": "unauthorized"})
                return
            if self.path == "/health":
                self._send_json(200, {"ok": True, "service": "whisperstash", "version": "1"})
                return
            self._send_json(404, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:
            if not self._is_authorized():
                self._send_json(401, {"ok": False, "error": "unauthorized"})
                return
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


def _looks_like_token(value: str) -> bool:
    if not value:
        return False
    if any(ch.isspace() for ch in value):
        return False
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-=")
    return all(ch in allowed for ch in value)


def _transform_text(passphrase: str, text: str, mode: str, integrity: bool, auto_wrap: bool) -> tuple[str, str]:
    selected = mode.lower().strip()
    if selected == "encrypt":
        return ("encrypt", encrypt_text(passphrase, text, integrity=integrity))
    if selected == "decrypt":
        return ("decrypt", decrypt_text(passphrase, text.strip()))
    if selected == "wrap":
        return ("wrap", wrap_text(passphrase, text, integrity=integrity))
    if selected == "unwrap":
        return ("unwrap", unwrap_text(passphrase, text))
    if selected != "auto":
        raise ValueError(f"Unknown mode: {mode}")

    if "ENC[" in text:
        try:
            return ("unwrap", unwrap_text(passphrase, text))
        except Exception:
            pass

    stripped = text.strip()
    if _looks_like_token(stripped):
        try:
            return ("decrypt", decrypt_text(passphrase, stripped))
        except Exception:
            pass

    if auto_wrap:
        return ("wrap", wrap_text(passphrase, text, integrity=integrity))
    return ("encrypt", encrypt_text(passphrase, text, integrity=integrity))


def cmd_ui(args: argparse.Namespace) -> int:
    key = read_key(args.key)
    ui_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisperstash_ui")

    def read_asset(name: str) -> bytes:
        path = os.path.join(ui_dir, name)
        with open(path, "rb") as f:
            return f.read()

    assets = {
        "/": ("text/html; charset=utf-8", read_asset("index.html")),
        "/index.html": ("text/html; charset=utf-8", read_asset("index.html")),
        "/app.js": ("application/javascript; charset=utf-8", read_asset("app.js")),
        "/styles.css": ("text/css; charset=utf-8", read_asset("styles.css")),
    }

    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            self._send_json(200, {"ok": True})

        def do_GET(self) -> None:
            if self.path == "/api/health":
                self._send_json(200, {"ok": True, "service": "whisperstash-ui"})
                return
            asset = assets.get(self.path)
            if asset is None:
                self._send_json(404, {"ok": False, "error": "not found"})
                return
            content_type, body = asset
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if self.path != "/api/transform":
                self._send_json(404, {"ok": False, "error": "not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._send_json(400, {"ok": False, "error": "invalid json"})
                return

            try:
                text = str(data.get("text", ""))
                mode = str(data.get("mode", "auto"))
                integrity = bool(data.get("integrity", False))
                auto_wrap = bool(data.get("auto_wrap", False))
                if text == "":
                    self._send_json(200, {"ok": True, "mode": mode, "output": ""})
                    return
                detected_mode, output = _transform_text(key, text, mode, integrity, auto_wrap)
                self._send_json(200, {"ok": True, "mode": detected_mode, "output": output})
            except Exception as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})

        def log_message(self, fmt: str, *args) -> None:
            if not args:
                return

    server = HTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"whisperstash ui listening on {url}")
    print("Press Ctrl+C to stop.")
    if not args.no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nUI stopped.")
    finally:
        server.server_close()
    return 0


def cmd_b64_to_enc(args: argparse.Namespace) -> int:
    key = read_key(args.key)
    raw_b64 = _read_file_text(args.in_file).strip()
    try:
        decoded_bytes = base64.b64decode(raw_b64, validate=True)
    except binascii.Error as exc:
        raise ValueError(f"Invalid base64 input: {exc}") from exc
    try:
        plain = decoded_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Decoded base64 is not valid UTF-8 text.") from exc

    token = encrypt_text(key, plain, integrity=args.integrity)
    out_file = args.out_file if args.out_file else _default_enc_output_path(args.in_file)
    _write_file_text(out_file, token + "\n")
    print(f"Wrote encrypted token to {out_file}")
    return 0


def cmd_file_encrypt(args: argparse.Namespace) -> int:
    key = read_key(args.key)
    in_file = args.in_file if args.in_file else input("Enter file path to encrypt (type /exit to cancel): ").strip()
    if in_file.lower() in {"/exit", "exit", "quit", "q"}:
        raise ValueError("Cancelled.")
    if not in_file:
        raise ValueError("Input file path cannot be empty.")
    if not os.path.isfile(in_file):
        raise ValueError(f"Input file not found: {in_file}")

    with open(in_file, "rb") as f:
        data = f.read()
    b64_text = base64.b64encode(data).decode("ascii")
    token = encrypt_text(key, b64_text, integrity=args.integrity)

    out_file = args.out_file if args.out_file else _default_enc_output_path(in_file)
    _write_file_text(out_file, token + "\n")
    print(f"Wrote encrypted file token to {out_file}")
    return 0


def cmd_batch_encrypt(args: argparse.Namespace) -> int:
    key = read_key(args.key)
    in_dir = os.path.abspath(args.in_dir)
    out_dir = os.path.abspath(args.out_dir) if args.out_dir else None
    count = 0
    include = args.include if args.include else ["*"]
    for in_file, rel_path in _iter_matched_files(in_dir, include, args.exclude):
        rel_out = f"{rel_path}.enc"
        out_file = os.path.join(out_dir, rel_out) if out_dir else _default_enc_output_path(in_file)
        if args.dry_run:
            print(f"DRY-RUN encrypt: {in_file} -> {out_file}")
            count += 1
            continue
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        with open(in_file, "rb") as f:
            data = f.read()
        b64_text = base64.b64encode(data).decode("ascii")
        token = encrypt_text(key, b64_text, integrity=args.integrity)
        _write_file_text(out_file, token + "\n")
        print(f"Encrypted: {in_file} -> {out_file}")
        count += 1
    print(f"Processed {count} file(s).")
    return 0


def cmd_file_decrypt(args: argparse.Namespace) -> int:
    key = read_key(args.key)
    in_file = args.in_file if args.in_file else input("Enter .enc file path to decrypt (type /exit to cancel): ").strip()
    if in_file.lower() in {"/exit", "exit", "quit", "q"}:
        raise ValueError("Cancelled.")
    if not in_file:
        raise ValueError("Input file path cannot be empty.")
    if not os.path.isfile(in_file):
        raise ValueError(f"Input file not found: {in_file}")

    token = _read_file_text(in_file).strip()
    b64_text = decrypt_text(key, token)
    try:
        data = base64.b64decode(b64_text.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError) as exc:
        raise ValueError(f"Decrypted token does not contain valid base64 file data: {exc}") from exc

    out_file = args.out_file if args.out_file else _default_dec_output_path(in_file)
    with open(out_file, "wb") as f:
        f.write(data)
    print(f"Wrote decrypted file to {out_file}")
    return 0


def cmd_batch_decrypt(args: argparse.Namespace) -> int:
    key = read_key(args.key)
    in_dir = os.path.abspath(args.in_dir)
    out_dir = os.path.abspath(args.out_dir) if args.out_dir else None
    count = 0
    include = args.include if args.include else ["*.enc"]
    for in_file, rel_path in _iter_matched_files(in_dir, include, args.exclude):
        rel_out = _default_dec_output_path(rel_path)
        out_file = os.path.join(out_dir, rel_out) if out_dir else _default_dec_output_path(in_file)
        if args.dry_run:
            print(f"DRY-RUN decrypt: {in_file} -> {out_file}")
            count += 1
            continue
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        token = _read_file_text(in_file).strip()
        b64_text = decrypt_text(key, token)
        try:
            data = base64.b64decode(b64_text.encode("ascii"), validate=True)
        except (binascii.Error, UnicodeEncodeError) as exc:
            raise ValueError(f"Decrypted token does not contain valid base64 file data: {in_file}: {exc}") from exc
        with open(out_file, "wb") as f:
            f.write(data)
        print(f"Decrypted: {in_file} -> {out_file}")
        count += 1
    print(f"Processed {count} file(s).")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    checks: list[tuple[str, bool, str]] = []

    if sys.platform == "win32":
        bin_dir = os.path.join(os.path.expanduser("~"), "bin")
        launcher = os.path.join(bin_dir, "whisperstash.cmd")
    else:
        bin_dir = os.path.join(os.path.expanduser("~"), "bin")
        launcher = os.path.join(bin_dir, "whisperstash")

    checks.append(("launcher_exists", os.path.exists(launcher), launcher))
    path_parts = [p.rstrip("\\/") for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    checks.append(("path_contains_bin", bin_dir.rstrip("\\/") in path_parts, bin_dir))

    home = os.environ.get("WHISPERSTASH_HOME") or os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "whisperstash"
    )
    if not home or home == "whisperstash":
        home = os.path.expanduser("~/.whisperstash")
    py = os.path.join(home, ".venv", "Scripts" if sys.platform == "win32" else "bin", "python.exe" if sys.platform == "win32" else "python")
    checks.append(("venv_python_exists", os.path.exists(py), py))

    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=1.0) as resp:
            ok = resp.status == 200
            detail = f"status={resp.status}"
    except Exception as exc:
        ok = False
        detail = str(exc)
    checks.append(("daemon_health", ok, detail))

    ext_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisperstash_chrome")
    manifest_path = os.path.join(ext_dir, "manifest.json")
    checks.append(("extension_manifest_exists", os.path.exists(manifest_path), manifest_path))
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            perms = set(manifest.get("permissions", []))
            unexpected = sorted(perms.intersection({"storage", "scripting"}))
            checks.append(("extension_permissions_minimal", len(unexpected) == 0, f"unexpected={unexpected or 'none'}"))
        except Exception as exc:
            checks.append(("extension_permissions_minimal", False, str(exc)))

    failures = 0
    for name, ok, detail in checks:
        status = "OK" if ok else "FAIL"
        print(f"{status:4} {name}: {detail}")
        if not ok:
            failures += 1

    if failures == 0:
        print("Doctor: all checks passed.")
        return 0
    print(f"Doctor: {failures} check(s) failed.")
    return 1


def _read_file_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_file_text(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _read_text_with_prompt(in_file: str | None, prompt: str, multiline: bool = False) -> str:
    if in_file is not None:
        return _read_file_text(in_file)
    if not multiline:
        value = input(f"{prompt} (type /exit to cancel): ").strip()
        if value.lower() in {"/exit", "exit", "quit", "q"}:
            raise ValueError("Cancelled.")
        if not value:
            raise ValueError("Input cannot be empty.")
        return value

    print(f"{prompt} Type EOF or a blank line when finished (or /exit to cancel).")
    lines: list[str] = []
    while True:
        line = input()
        stripped = line.strip().lower()
        if stripped in {"/exit", "exit", "quit", "q"}:
            raise ValueError("Cancelled.")
        if line == "" and lines:
            break
        if line == "EOF":
            break
        lines.append(line)
    value = "\n".join(lines).strip()
    if not value:
        raise ValueError("Input cannot be empty.")
    return value


def _read_clipboard_text() -> str:
    if sys.platform == "win32":
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            value = proc.stdout
            if value:
                return value
        raise ValueError("Unable to read clipboard via PowerShell.")

    for cmd in (["pbpaste"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]):
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
    raise ValueError("Unable to read clipboard (supported tools: pbpaste/xclip/xsel).")


def _write_clipboard_text(value: str) -> None:
    if sys.platform == "win32":
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Set-Clipboard"],
            input=value,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise ValueError("Unable to write clipboard via PowerShell.")
        return

    for cmd in (["pbcopy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
        proc = subprocess.run(cmd, input=value, text=True, capture_output=True, check=False)
        if proc.returncode == 0:
            return
    raise ValueError("Unable to write clipboard (supported tools: pbcopy/xclip/xsel).")


def _default_enc_output_path(in_file: str) -> str:
    root, _ = os.path.splitext(in_file)
    if not root:
        return f"{in_file}.enc"
    return f"{root}.enc"


def _default_dec_output_path(in_file: str) -> str:
    if in_file.lower().endswith(".enc"):
        return in_file[:-4]
    return f"{in_file}.out"


def _run_interactive_mode(parser: argparse.ArgumentParser) -> int:
    print("WhisperStash interactive mode")
    print("Type a command (e.g. encrypt --text \"hello\"), or 'help', or 'exit'.")
    while True:
        try:
            raw = input("whisperstash> ").strip()
        except EOFError:
            print("")
            return 0
        except KeyboardInterrupt:
            print("")
            return 0
        if not raw:
            continue
        if raw.lower() in {"exit", "quit", "q"}:
            return 0
        if raw.lower() in {"help", "h", "?"}:
            parser.print_help()
            continue
        raw = _expand_interactive_shortcuts(raw)
        try:
            args = parser.parse_args(shlex.split(raw))
        except SystemExit:
            continue
        code = _execute_args(args)
        if code != 0:
            print(f"(exit code {code})")


def _execute_args(args: argparse.Namespace) -> int:
    if args.command in {"encrypt", "wrap", "unwrap"}:
        if args.text is not None and args.in_file is not None:
            raise ValueError("Use only one of --text or --in-file")
        if getattr(args, "from_clipboard", False) and (args.text is not None or args.in_file is not None):
            raise ValueError("Use only one of --from-clipboard, --text, or --in-file")
    if args.command in {"decrypt"}:
        if args.token is not None and args.in_file is not None:
            raise ValueError("Use only one of --token or --in-file")
        if getattr(args, "from_clipboard", False) and (args.token is not None or args.in_file is not None):
            raise ValueError("Use only one of --from-clipboard, --token, or --in-file")

    return args.func(args)


def _expand_interactive_shortcuts(raw: str) -> str:
    parts = shlex.split(raw)
    if not parts:
        return raw
    cmd = parts[0]
    rest = parts[1:]
    if not rest:
        return raw
    if any(p.startswith("-") for p in rest):
        return raw

    if cmd in {"encrypt", "wrap", "unwrap"}:
        return f'{cmd} --text {shlex.quote(" ".join(rest))}'
    if cmd == "decrypt":
        return f'{cmd} --token {shlex.quote(" ".join(rest))}'
    return raw


def _iter_matched_files(in_dir: str, include: list[str], exclude: list[str]) -> list[tuple[str, str]]:
    if not os.path.isdir(in_dir):
        raise ValueError(f"Input directory not found: {in_dir}")
    out: list[tuple[str, str]] = []
    for root, _, files in os.walk(in_dir):
        files.sort()
        for name in files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, in_dir).replace(os.sep, "/")
            if include and not any(fnmatch.fnmatch(rel, pat) for pat in include):
                continue
            if exclude and any(fnmatch.fnmatch(rel, pat) for pat in exclude):
                continue
            out.append((full, rel))
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="All-in-one encrypted text toolkit for CLI + browser extension.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("encrypt", help="Encrypt text to token")
    p.add_argument("--text", help="Plain text")
    p.add_argument("--in-file", help="Read plain text from file")
    p.add_argument("--from-clipboard", action="store_true", help="Read plain text from clipboard")
    p.add_argument("--copy", action="store_true", help="Copy resulting token to clipboard")
    p.add_argument("--key", help="Passphrase (avoid shell history)")
    p.add_argument("--integrity", action="store_true", help="Use NC2 token format with HMAC integrity check")
    p.set_defaults(func=cmd_encrypt)

    p = sub.add_parser("decrypt", help="Decrypt token to plain text")
    p.add_argument("--token", help="Encrypted token")
    p.add_argument("--in-file", help="Read token from file")
    p.add_argument("--from-clipboard", action="store_true", help="Read token from clipboard")
    p.add_argument("--copy", action="store_true", help="Copy resulting plain text to clipboard")
    p.add_argument("--key", help="Passphrase (avoid shell history)")
    p.set_defaults(func=cmd_decrypt)

    p = sub.add_parser("wrap", help="Encrypt and wrap as ENC[...] ")
    p.add_argument("--text", help="Plain text")
    p.add_argument("--in-file", help="Read plain text from file")
    p.add_argument("--from-clipboard", action="store_true", help="Read plain text from clipboard")
    p.add_argument("--copy", action="store_true", help="Copy resulting wrapped text to clipboard")
    p.add_argument("--key", help="Passphrase (avoid shell history)")
    p.add_argument("--integrity", action="store_true", help="Use NC2 token format with HMAC integrity check")
    p.set_defaults(func=cmd_wrap)

    p = sub.add_parser("unwrap", help="Decrypt all ENC[...] blocks in text")
    p.add_argument("--text", help="Input text containing ENC[...] blocks")
    p.add_argument("--in-file", help="Read input from file")
    p.add_argument("--from-clipboard", action="store_true", help="Read input text from clipboard")
    p.add_argument("--copy", action="store_true", help="Copy resulting unwrapped text to clipboard")
    p.add_argument("--key", help="Passphrase (avoid shell history)")
    p.set_defaults(func=cmd_unwrap)

    p = sub.add_parser("view", help="Decrypt token file and view in pager")
    p.add_argument("file", help="File containing a token")
    p.add_argument("--key", help="Passphrase (avoid shell history)")
    p.set_defaults(func=cmd_view)

    p = sub.add_parser("edit", help="Decrypt token file, edit, and re-encrypt")
    p.add_argument("file", help="File containing a token")
    p.add_argument("--key", help="Passphrase (avoid shell history)")
    p.add_argument("--integrity", action="store_true", help="Write updated file as NC2 integrity token")
    p.set_defaults(func=cmd_edit)

    p = sub.add_parser("server", help="Run localhost API for browser extension")
    p.add_argument("--host", default="127.0.0.1", help="Host bind address")
    p.add_argument("--port", type=int, default=8765, help="Port")
    p.add_argument("--key", help="Passphrase (avoid shell history)")
    p.add_argument("--auth-token", help="Optional bearer token required by API clients")
    p.set_defaults(func=cmd_server)

    p = sub.add_parser("ui", help="Run modern local UI for live encrypt/decrypt")
    p.add_argument("--host", default="127.0.0.1", help="Host bind address")
    p.add_argument("--port", type=int, default=8787, help="Port")
    p.add_argument("--key", help="Passphrase (avoid shell history)")
    p.add_argument("--no-open", action="store_true", help="Do not auto-open browser")
    p.set_defaults(func=cmd_ui)

    p = sub.add_parser("b64-to-enc", help="Decode base64 file and write encrypted .enc token file")
    p.add_argument("--in-file", required=True, help="Input file containing base64 text")
    p.add_argument("--out-file", help="Output .enc file path (default: input with .enc extension)")
    p.add_argument("--key", help="Passphrase (avoid shell history)")
    p.add_argument("--integrity", action="store_true", help="Use NC2 token format with HMAC integrity check")
    p.set_defaults(func=cmd_b64_to_enc)

    p = sub.add_parser("file-encrypt", help="Base64-encode any file and encrypt into .enc token file")
    p.add_argument("--in-file", help="Input file path (if omitted, prompt interactively)")
    p.add_argument("--out-file", help="Output .enc file path (default: input with .enc extension)")
    p.add_argument("--key", help="Passphrase (avoid shell history)")
    p.add_argument("--integrity", action="store_true", help="Use NC2 token format with HMAC integrity check")
    p.set_defaults(func=cmd_file_encrypt)

    p = sub.add_parser("file-decrypt", help="Decrypt .enc token file and restore original file bytes")
    p.add_argument("--in-file", help="Input .enc file path (if omitted, prompt interactively)")
    p.add_argument("--out-file", help="Output file path (default: remove .enc suffix)")
    p.add_argument("--key", help="Passphrase (avoid shell history)")
    p.set_defaults(func=cmd_file_decrypt)

    p = sub.add_parser("batch", help="Batch file-encrypt/file-decrypt folders with include/exclude filters")
    batch_sub = p.add_subparsers(dest="batch_command", required=True)

    p_batch_enc = batch_sub.add_parser("encrypt", help="Encrypt matched files in a folder")
    p_batch_enc.add_argument("--in-dir", required=True, help="Input directory")
    p_batch_enc.add_argument("--out-dir", help="Output directory (default: alongside input files)")
    p_batch_enc.add_argument("--include", action="append", help="Glob include pattern on relative path (repeatable)")
    p_batch_enc.add_argument("--exclude", action="append", default=[], help="Glob exclude pattern on relative path")
    p_batch_enc.add_argument("--dry-run", action="store_true", help="Show planned operations without writing files")
    p_batch_enc.add_argument("--key", help="Passphrase (avoid shell history)")
    p_batch_enc.add_argument("--integrity", action="store_true", help="Use NC2 token format with HMAC integrity check")
    p_batch_enc.set_defaults(func=cmd_batch_encrypt)

    p_batch_dec = batch_sub.add_parser("decrypt", help="Decrypt matched .enc files in a folder")
    p_batch_dec.add_argument("--in-dir", required=True, help="Input directory")
    p_batch_dec.add_argument("--out-dir", help="Output directory (default: alongside input files)")
    p_batch_dec.add_argument("--include", action="append", help="Glob include pattern on relative path (repeatable)")
    p_batch_dec.add_argument("--exclude", action="append", default=[], help="Glob exclude pattern on relative path")
    p_batch_dec.add_argument("--dry-run", action="store_true", help="Show planned operations without writing files")
    p_batch_dec.add_argument("--key", help="Passphrase (avoid shell history)")
    p_batch_dec.set_defaults(func=cmd_batch_decrypt)

    p = sub.add_parser("doctor", help="Run installation and runtime diagnostics")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("key", help="Manage default key/passphrase")
    key_sub = p.add_subparsers(dest="key_command", required=True)

    p_key_set = key_sub.add_parser("set", help="Save default key")
    p_key_set.add_argument("--key", help="Passphrase (avoid shell history)")
    p_key_set.set_defaults(func=cmd_key_set)

    p_key_clear = key_sub.add_parser("clear", help="Remove default key")
    p_key_clear.set_defaults(func=cmd_key_clear)

    p_key_status = key_sub.add_parser("status", help="Show default key status")
    p_key_status.set_defaults(func=cmd_key_status)

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
    if len(sys.argv) == 1:
        if sys.stdin.isatty():
            return _run_interactive_mode(parser)
        parser.print_help()
        return 1

    args = parser.parse_args()
    try:
        return _execute_args(args)
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
