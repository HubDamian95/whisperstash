# WhisperStash (CLI + Chrome extension)

## Files
- `whisperstash.py`: all-in-one CLI + localhost API daemon
- `whisperstash_chrome/`: Chrome extension (load unpacked)
- `whisperstash_chrome.zip`: zipped extension folder

## 1) CLI usage

Encrypt text:
```bash
python3 whisperstash.py encrypt --text "hello"
```

Wrap text as `ENC[...]`:
```bash
python3 whisperstash.py wrap --text "secret message"
```

Decrypt token:
```bash
python3 whisperstash.py decrypt --token "<TOKEN>"
```

Unwrap text containing one or many `ENC[...]` blocks:
```bash
python3 whisperstash.py unwrap --text "my note ENC[...] and more"
```

View/edit token file transparently:
```bash
python3 whisperstash.py view my_note.enc
python3 whisperstash.py edit my_note.enc
```

## 2) Start local daemon for browser integration
```bash
python3 whisperstash.py server
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
