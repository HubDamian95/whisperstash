import argparse
import base64
from pathlib import Path

import whisperstash as ws


def test_encrypt_decrypt_roundtrip():
    token = ws.encrypt_text("k1", "hello")
    assert ws.decrypt_text("k1", token) == "hello"


def test_integrity_mode_rejects_wrong_key():
    token = ws.encrypt_text("k1", "hello", integrity=True)
    try:
        ws.decrypt_text("k2", token)
        assert False, "Expected integrity error for wrong key"
    except ValueError as exc:
        assert "Integrity check failed" in str(exc)


def test_default_key_file_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("WHISPERSTASH_HOME", str(tmp_path))
    args = argparse.Namespace(key="abc123")
    assert ws.cmd_key_set(args) == 0
    assert ws._read_default_key() == "abc123"
    assert ws.cmd_key_clear(argparse.Namespace()) == 0
    assert ws._read_default_key() is None


def test_file_encrypt_and_decrypt_roundtrip(tmp_path):
    input_file = tmp_path / "data.bin"
    enc_file = tmp_path / "data.enc"
    out_file = tmp_path / "restored.bin"
    input_file.write_bytes(b"\x00\x01hello\xff")

    enc_args = argparse.Namespace(in_file=str(input_file), out_file=str(enc_file), key="k1", integrity=False)
    assert ws.cmd_file_encrypt(enc_args) == 0

    dec_args = argparse.Namespace(in_file=str(enc_file), out_file=str(out_file), key="k1")
    assert ws.cmd_file_decrypt(dec_args) == 0
    assert out_file.read_bytes() == input_file.read_bytes()


def test_b64_to_enc_roundtrip(tmp_path):
    b64_file = tmp_path / "payload.b64"
    enc_file = tmp_path / "payload.enc"
    data = base64.b64encode("content".encode("utf-8")).decode("ascii")
    b64_file.write_text(data, encoding="utf-8")

    args = argparse.Namespace(in_file=str(b64_file), out_file=str(enc_file), key="k1", integrity=True)
    assert ws.cmd_b64_to_enc(args) == 0
    token = enc_file.read_text(encoding="utf-8").strip()
    assert ws.decrypt_text("k1", token) == "content"

