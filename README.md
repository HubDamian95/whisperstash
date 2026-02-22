# WhisperStash

When creating this toolkit, what I had in mind is that our data is constantly being scraped by AI. I wanted an easy tool that I can use with some sort of "key" that I can share with bunch of my family and friends such that only the people I share the key with will understand, and then we will be able to hide what we're talking about. This is specifically important as more governments around the world are issuing ID checks, social media bans and information sharing is becoming less and less possible for people around the world. 

I appreciate that this tool can also be used for nefarious purposes, although I hope it won't be. Please stay safe out there. 

Local-first encryption toolkit with:
- CLI workflows for text and files
- Local browser UI (`whisperstash ui`)
- Chrome extension support via localhost daemon

No cloud backend. Your data stays on your machine.

## Quick Install

Linux/macOS:
```bash
curl -fsSL https://raw.githubusercontent.com/HubDamian95/whisperstash/main/install.sh | bash
```

Windows (PowerShell, run in current shell):
```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
irm https://raw.githubusercontent.com/HubDamian95/whisperstash/main/install.ps1 | iex
```

Windows (`cmd.exe`):
```bat
powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/HubDamian95/whisperstash/main/install.ps1 | iex"
```

Verify:
```bash
whisperstash --help
```

## Fast Start

Encrypt/decrypt text:
```bash
whisperstash encrypt --text "hello"
whisperstash decrypt --token "<TOKEN>"
```

Wrap/unwrap `ENC[...]`:
```bash
whisperstash wrap --text "secret"
whisperstash unwrap --text "note ENC[...]"
```

Set a default key (reused automatically):
```bash
whisperstash key set
whisperstash key status
whisperstash key clear
```

Run modern local UI:
```bash
whisperstash ui
```

## Modern UI (`whisperstash ui`)

Tabs:
- `Text`: live auto/manual encrypt/decrypt/wrap/unwrap
- `Files`: `file-encrypt`, `file-decrypt`, `b64-to-enc`
- `Batch`: folder encrypt/decrypt with include/exclude and dry-run
- `Tools`: doctor output + key status

Notes:
- UI API uses session token protection.
- `--auth-token` can set a fixed token.

Examples:
```bash
whisperstash ui --port 8787 --no-open
whisperstash ui --auth-token "my-fixed-ui-token"
```

## CLI Features

Text features:
```bash
whisperstash encrypt --text "hello"
whisperstash decrypt --token "<TOKEN>"
whisperstash wrap --text "secret"
whisperstash unwrap --text "contains ENC[...]"
```

Clipboard helpers:
```bash
whisperstash encrypt --from-clipboard --copy
whisperstash decrypt --from-clipboard --copy
whisperstash wrap --from-clipboard --copy
whisperstash unwrap --from-clipboard --copy
```

Integrity mode (`NC2` + HMAC):
```bash
whisperstash encrypt --text "hello" --integrity
whisperstash wrap --text "secret" --integrity
```

Interactive mode:
```bash
whisperstash
```
- No-arg launch opens interactive shell.
- Shortcuts like `encrypt hello` and `decrypt <TOKEN>` are supported.
- Multiline prompts finish with `EOF` or a blank line.

File features:
```bash
whisperstash b64-to-enc --in-file payload.b64
whisperstash file-encrypt --in-file photo.jpg
whisperstash file-decrypt --in-file photo.jpg.enc
```

Batch features:
```bash
whisperstash batch encrypt --in-dir ./docs --include "*.txt" --dry-run
whisperstash batch encrypt --in-dir ./docs --out-dir ./docs_enc --include "*.txt"
whisperstash batch decrypt --in-dir ./docs_enc --out-dir ./docs_out --include "*.enc"
```

Diagnostics:
```bash
whisperstash doctor
```

## Browser Daemon + Chrome Extension

Start daemon for extension:
```bash
whisperstash server
```

Optional API token:
```bash
whisperstash server --auth-token "my-local-token"
# or
WHISPERSTASH_AUTH_TOKEN=my-local-token whisperstash server
```

Load extension:
1. Open `chrome://extensions`
2. Enable `Developer mode`
3. Click `Load unpacked`
4. Select `whisperstash_chrome`

## Binary Builds

Local one-file binaries:

Linux:
```bash
./scripts/build-linux.sh
# output: dist/release/whisperstash-linux-x86_64
```

Windows (PowerShell):
```powershell
./scripts/build-windows.ps1
# output: dist/release/whisperstash-windows-x86_64.exe
```

Notes:
- Windows icon source: `Whisperstash_logo_small_128.png`
- UI assets are bundled in release binaries

## GitHub Release Flow

Tag and push:
```bash
git tag v1.0.0
git push origin v1.0.0
```

`release.yml` builds Linux + Windows binaries and uploads them as release assets.

## Security Notes

- Prefer interactive key input over `--key` in shell history.
- Decrypted content is visible in terminal/browser once processed.
- Windows default key storage uses DPAPI.

## Privacy

- Policy file: `PRIVACY.md`
- Direct URL: `https://raw.githubusercontent.com/HubDamian95/whisperstash/main/PRIVACY.md`
