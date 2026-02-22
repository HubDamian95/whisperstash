# WhisperStash (CLI + Chrome extension)

## One-step install

```bash
curl -fsSL https://raw.githubusercontent.com/HubDamian95/whisperstash/main/install.sh | bash
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

Unwrap text containing one or many `ENC[...]` blocks:
```bash
whisperstash unwrap --text "my note ENC[...] and more"
```

View/edit token file transparently:
```bash
whisperstash view my_note.enc
whisperstash edit my_note.enc
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
