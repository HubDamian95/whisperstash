# WhisperStash (CLI + Chrome extension)

Local-first privacy toolkit for encrypting and decrypting text quickly from both terminal and browser.
  - CLI commands to encrypt/decrypt text, wrap secrets as ENC[...], unwrap them, and transparently view/edit encrypted note files.
  - A local daemon (whisperstash server) that keeps your passphrase in memory for the session and exposes localhost endpoints.
  - A Chrome extension that can decrypt ENC[...] blocks on web pages by calling your local daemon.

  Security model:

  - Passphrase-based AES-GCM encryption with PBKDF2 key derivation.
  - No cloud service required; browser integration talks to 127.0.0.1.
  - Best practice is interactive passphrase entry (avoid putting keys in command history).


  Why is it important? 
  - Protects private notes/messages if files leak, sync gets compromised, or screenshots/logs are shared.
  - Keeps secrets unreadable by default (ENC[...]) while still being easy to decrypt when you need them.
  - Works locally, so you’re not forced to trust a third-party server with raw content.
  - Gives a practical workflow: encrypt in CLI, decrypt in browser/page context only on your device.
  - Reduces human error by making secure behavior the easy behavior (one command, one local daemon, one extension button).

## One-step install

Linux/macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/HubDamian95/whisperstash/main/install.sh | bash
```

Windows (PowerShell):

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
irm https://raw.githubusercontent.com/HubDamian95/whisperstash/main/install.ps1 | iex
```

If you run install from `cmd.exe`, use:
```bat
powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/HubDamian95/whisperstash/main/install.ps1 | iex"
```

After install:

```bash
whisperstash --help
```

Update later by re-running the same command.

## Binary builds (single-file runtime)

Build Linux binary locally:
```bash
./scripts/build-linux.sh
```
Output:
```bash
dist/release/whisperstash-linux-x86_64
```

Build Windows binary locally (PowerShell):
```powershell
./scripts/build-windows.ps1
```
Output:
```powershell
dist/release/whisperstash-windows-x86_64.exe
```

## GitHub release flow

This repo includes `.github/workflows/release.yml` which:
- triggers on tags matching `v*`
- builds Linux and Windows binaries
- uploads binaries as GitHub Release assets

Create a release tag:
```bash
git tag v1.0.0
git push origin v1.0.0
```

## Files
- `whisperstash.py`: all-in-one CLI + localhost API daemon
- `encsuite.py`: compatibility launcher
- `whisperstash_chrome/`: Chrome extension (load unpacked)

## 1) CLI usage

Encrypt text:
```bash
whisperstash encrypt --text "hello"
# with integrity protection (NC2 + HMAC):
whisperstash encrypt --text "hello" --integrity
```

Interactive multiline mode:
```bash
whisperstash encrypt
# paste/type lines, then enter EOF on its own line to finish
```

Wrap text as `ENC[...]`:
```bash
whisperstash wrap --text "secret message"
# with integrity protection:
whisperstash wrap --text "secret message" --integrity
```

Decrypt token:
```bash
whisperstash decrypt --token "<TOKEN>"
```

Clipboard helpers:
```bash
whisperstash encrypt --from-clipboard --copy
whisperstash decrypt --from-clipboard --copy
whisperstash wrap --from-clipboard --copy
whisperstash unwrap --from-clipboard --copy
```

Set a default key once (used automatically by encrypt/decrypt/wrap/unwrap/view/edit/server):
```bash
whisperstash key set
```

Manage default key:
```bash
whisperstash key status
whisperstash key clear
```

Unwrap text containing one or many `ENC[...]` blocks:
```bash
whisperstash unwrap --text "my note ENC[...] and more"
```

View/edit token file transparently:
```bash
whisperstash view my_note.enc
whisperstash edit my_note.enc
```

Decode a base64 text file, encrypt it, and write a `.enc` file:
```bash
whisperstash b64-to-enc --in-file secret.b64
# optional output path:
whisperstash b64-to-enc --in-file secret.b64 --out-file secret.enc
# optional integrity token format:
whisperstash b64-to-enc --in-file secret.b64 --integrity
```

Encrypt any file into a `.enc` token file (file bytes -> base64 -> encrypted token):
```bash
whisperstash file-encrypt --in-file photo.jpg
# optional output path:
whisperstash file-encrypt --in-file photo.jpg --out-file photo.enc
# interactive prompt mode:
whisperstash file-encrypt
# optional integrity token format:
whisperstash file-encrypt --in-file photo.jpg --integrity
```

Decrypt a `.enc` token file back to original bytes:
```bash
whisperstash file-decrypt --in-file photo.enc
# optional output path:
whisperstash file-decrypt --in-file photo.enc --out-file photo_restored.jpg
# interactive prompt mode:
whisperstash file-decrypt
```

Batch folder mode with include/exclude and dry-run:
```bash
whisperstash batch encrypt --in-dir ./docs --include "*.txt" --exclude "tmp/*" --dry-run
whisperstash batch encrypt --in-dir ./docs --out-dir ./docs_enc --include "*.txt"
whisperstash batch decrypt --in-dir ./docs_enc --out-dir ./docs_restored --include "*.enc"
```
Defaults:
- `batch encrypt`: includes all files (`*`), writes `<name>.<ext>.enc`
- `batch decrypt`: includes `*.enc`, writes output with `.enc` suffix removed

Installation/runtime diagnostics:
```bash
whisperstash doctor
```

## 2) Start local daemon for browser integration
```bash
whisperstash server
```
It prompts for your passphrase once and keeps it in memory until you stop it.

Optional hardening with bearer token:
```bash
whisperstash server --auth-token "my-local-token"
```
Then enter the same token in the extension popup field.

Equivalent via environment variable:
```bash
WHISPERSTASH_AUTH_TOKEN=my-local-token whisperstash server
```

## CLI command reference
```bash
whisperstash encrypt
whisperstash decrypt
whisperstash wrap
whisperstash unwrap
whisperstash view <file.enc>
whisperstash edit <file.enc>
whisperstash server
whisperstash b64-to-enc --in-file <file.b64>
whisperstash file-encrypt --in-file <file>
whisperstash file-decrypt --in-file <file.enc>
whisperstash batch encrypt --in-dir <dir>
whisperstash batch decrypt --in-dir <dir>
whisperstash doctor
whisperstash key set
whisperstash key status
whisperstash key clear
```

No-argument behavior:
- Running `whisperstash` with no args starts interactive mode.
- This is useful for double-clicking the Windows `.exe` binary (window stays open and accepts commands).
- Interactive shortcuts are supported (examples: `encrypt hello`, `decrypt <TOKEN>`, `wrap my secret`).
- In interactive multiline prompts, finish with `EOF` or just an empty line.

## 3) Load Chrome extension
1. Open `chrome://extensions`
2. Enable `Developer mode`
3. Click `Load unpacked`
4. Select folder: `whisperstash_chrome`

Then:
- Open the extension popup
- Click `Check local server`
- Click `Decrypt ENC[...] on this page`

## Security notes
- Do not hardcode your passphrase.
- Prefer interactive key entry (no `--key`) to avoid shell history leakage.
- Any decrypted page content becomes visible in the tab after replacement.
- On Windows, `whisperstash key set` stores the default key protected with DPAPI (user/machine scoped).
- Use `--integrity` to produce NC2 tokens with HMAC integrity checks.

## Privacy Policy
- `PRIVACY.md`
- Direct URL for Chrome Web Store field: `https://raw.githubusercontent.com/HubDamian95/whisperstash/main/PRIVACY.md`
