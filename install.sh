#!/usr/bin/env bash
set -euo pipefail

# Voice Input — one-time setup script
# Run with: sudo bash install.sh

PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
USER_NAME="${SUDO_USER:-$USER}"

echo "=== Voice Input Setup ==="
echo "Project dir : $PROJ_DIR"
echo "User        : $USER_NAME"
echo ""

# 1. Add user to 'input' group (for /dev/input/* and /dev/uinput access)
if id -nG "$USER_NAME" | grep -qw input; then
    echo "[ok] $USER_NAME is already in the 'input' group"
else
    echo "[+]  Adding $USER_NAME to 'input' group..."
    usermod -aG input "$USER_NAME"
    echo "     Done. You MUST log out and back in for this to take effect."
fi

# 2. udev rule so /dev/uinput is accessible by the 'input' group
UDEV_RULE="/etc/udev/rules.d/99-uinput-voice-input.rules"
if [ -f "$UDEV_RULE" ]; then
    echo "[ok] udev rule already exists at $UDEV_RULE"
else
    echo "[+]  Creating udev rule for /dev/uinput..."
    cat > "$UDEV_RULE" <<'EOF'
# Allow 'input' group to access /dev/uinput (needed by voice-input)
KERNEL=="uinput", GROUP="input", MODE="0660"
EOF
    udevadm control --reload-rules
    udevadm trigger /dev/uinput
    echo "     Done."
fi

# 3. Install systemd user service
SERVICE_DIR="/home/$USER_NAME/.config/systemd/user"
mkdir -p "$SERVICE_DIR"
cp "$PROJ_DIR/voice-input.service" "$SERVICE_DIR/voice-input.service"
# Fix ownership (we're running as root)
chown -R "$USER_NAME:$USER_NAME" "$SERVICE_DIR"
echo "[ok] Installed systemd user service"

# 4. Create log directory
LOG_DIR="/home/$USER_NAME/.local/share/voice-input"
mkdir -p "$LOG_DIR"
chown "$USER_NAME:$USER_NAME" "$LOG_DIR"
echo "[ok] Log directory ready at $LOG_DIR"

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Log out and log back in (so the 'input' group takes effect)"
echo "  2. Make sure ~/MATS/keys.sh exists and exports OPENAI_API_KEY"
echo "  3. Enable the service:"
echo "       systemctl --user daemon-reload"
echo "       systemctl --user enable --now voice-input"
echo "  4. Press Super+Shift+V to start recording!"
