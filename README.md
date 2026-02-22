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

## Files
- `whisperstash.py`: all-in-one CLI + localhost API daemon
- `encsuite.py`: compatibility launcher
- `whisperstash_chrome/`: Chrome extension (load unpacked)

## 1) CLI usage

Encrypt text:
```bash
whisperstash encrypt --text "hello"
```

Wrap text as `ENC[...]`:
```bash
whisperstash wrap --text "secret message"
```

Decrypt token:
```bash
whisperstash decrypt --token "<TOKEN>"
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
```

Encrypt any file into a `.enc` token file (file bytes -> base64 -> encrypted token):
```bash
whisperstash file-encrypt --in-file photo.jpg
# optional output path:
whisperstash file-encrypt --in-file photo.jpg --out-file photo.enc
# interactive prompt mode:
whisperstash file-encrypt
```

Decrypt a `.enc` token file back to original bytes:
```bash
whisperstash file-decrypt --in-file photo.enc
# optional output path:
whisperstash file-decrypt --in-file photo.enc --out-file photo_restored.jpg
# interactive prompt mode:
whisperstash file-decrypt
```

## 2) Start local daemon for browser integration
```bash
whisperstash server
```
It prompts for your passphrase once and keeps it in memory until you stop it.

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

## Privacy Policy
- `PRIVACY.md`
- Direct URL for Chrome Web Store field: `https://raw.githubusercontent.com/HubDamian95/whisperstash/main/PRIVACY.md`
