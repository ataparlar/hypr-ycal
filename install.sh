#!/usr/bin/env bash
set -euo pipefail

DEST_DIR="$HOME/.config/waybar-ycal"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

echo "=== Installing hypr-ycal Suite ==="

# Create directories
mkdir -p "$DEST_DIR/themes"
mkdir -p "$SYSTEMD_USER_DIR"

# Copy scripts and themes
cp -a bg.py "$DEST_DIR/"
cp -a popup.py "$DEST_DIR/"
cp -a bar.py "$DEST_DIR/"
cp -a toggle.sh "$DEST_DIR/"
cp -a switch-theme.sh "$DEST_DIR/"
cp -a credentials.json.example "$DEST_DIR/"
cp -a themes/* "$DEST_DIR/themes/"

# Set initial config and theme if not present
if [ ! -f "$DEST_DIR/config.json" ]; then
    cp -a config.json "$DEST_DIR/"
fi
if [ ! -f "$DEST_DIR/current_theme.json" ]; then
    cp "$DEST_DIR/themes/dark-pastel-grey-green.json" "$DEST_DIR/current_theme.json"
    echo "dark-pastel-grey-green" > "$DEST_DIR/.current-theme"
fi

# Ensure executables
chmod +x "$DEST_DIR/bg.py" "$DEST_DIR/popup.py" "$DEST_DIR/bar.py" "$DEST_DIR/toggle.sh" "$DEST_DIR/switch-theme.sh"

# Install systemd units
cp -a waybar-ycal.service "$SYSTEMD_USER_DIR/"
cp -a waybar-ycal-bg.service "$SYSTEMD_USER_DIR/"

systemctl --user daemon-reload

echo "✓ Files installed to $DEST_DIR"
echo "✓ Systemd units installed to $SYSTEMD_USER_DIR"
echo ""
echo "Next steps:"
echo "1. Follow Google Cloud Setup in README.md and place your credentials at:"
echo "   $DEST_DIR/credentials.json"
echo "2. Enable and start the services:"
echo "   systemctl --user enable --now waybar-ycal.service"
echo "   systemctl --user enable --now waybar-ycal-bg.service"
