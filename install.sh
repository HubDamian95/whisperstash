#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${WHISPERSTASH_REPO_URL:-https://github.com/HubDamian95/whisperstash.git}"
INSTALL_DIR="${WHISPERSTASH_HOME:-$HOME/.local/share/whisperstash}"
BIN_DIR="${WHISPERSTASH_BIN:-$HOME/.local/bin}"

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

need_cmd git
need_cmd python3

mkdir -p "$BIN_DIR"

if [ -d "$INSTALL_DIR/.git" ]; then
  git -C "$INSTALL_DIR" pull --ff-only
else
  rm -rf "$INSTALL_DIR"
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" -q install --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" -q install cryptography

cat >"$BIN_DIR/whisperstash" <<EOF
#!/usr/bin/env bash
exec "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/whisperstash.py" "\$@"
EOF
chmod +x "$BIN_DIR/whisperstash"

echo "Installed WhisperStash."
echo "Command: $BIN_DIR/whisperstash"
echo
echo "If command not found, add this to your shell profile:"
echo "  export PATH=\"$BIN_DIR:\$PATH\""
