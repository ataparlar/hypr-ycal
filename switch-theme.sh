#!/bin/bash
# Waybar-YCal Task Manager & Calendar Theme Switcher
# Usage:
#   switch-theme.sh                    (list available themes & active theme)
#   switch-theme.sh <theme-name>       (switch theme and reload dashboard)
#   switch-theme.sh <theme-name> --all (switch both task manager and waybar)

YCAL_DIR="$HOME/.config/waybar-ycal"
THEMES_DIR="$YCAL_DIR/themes"
CURRENT_FILE="$YCAL_DIR/.current-theme"
TARGET_THEME="$YCAL_DIR/current_theme.json"

list_themes() {
    echo "=========================================="
    echo "  Waybar-Ycal Dashboard Theme Switcher"
    echo "=========================================="
    active="unknown"
    if [ -f "$CURRENT_FILE" ]; then
        active=$(cat "$CURRENT_FILE")
    fi
    echo "Active Theme: $active"
    echo ""
    echo "Available Themes:"
    for f in "$THEMES_DIR"/*.json; do
        if [ -f "$f" ]; then
            tname=$(basename "$f" .json)
            if [ "$tname" = "$active" ]; then
                echo "  * $tname (active)"
            else
                echo "    $tname"
            fi
        fi
    done
    echo ""
    echo "To switch theme:"
    echo "  $0 <theme-name>"
    echo "  $0 <theme-name> --all   (also switch waybar if matching theme exists)"
    echo "=========================================="
}

SYNC_ALL=0
THEME_NAME=""

for arg in "$@"; do
    case "$arg" in
        --all|-a)
            SYNC_ALL=1
            ;;
        -h|--help)
            list_themes
            exit 0
            ;;
        *)
            if [ -z "$THEME_NAME" ]; then
                THEME_NAME="$arg"
            fi
            ;;
    esac
done

if [ -z "$THEME_NAME" ]; then
    list_themes
    exit 0
fi

THEME_NAME="${THEME_NAME%.json}"
THEME_SRC="$THEMES_DIR/${THEME_NAME}.json"

if [ ! -f "$THEME_SRC" ]; then
    echo "Error: Theme '$THEME_NAME' not found in $THEMES_DIR"
    echo ""
    list_themes
    exit 1
fi

# Apply theme
cp "$THEME_SRC" "$TARGET_THEME"
echo "$THEME_NAME" > "$CURRENT_FILE"
# Touch file to trigger inotify monitor
touch "$TARGET_THEME"

echo "Applied theme '$THEME_NAME' to desktop dashboard."

# Check if user requested syncing Waybar as well
if [ "$SYNC_ALL" -eq 1 ]; then
    WAYBAR_SWITCHER="$HOME/.config/waybar/switch-theme.sh"
    if [ -x "$WAYBAR_SWITCHER" ]; then
        case "$THEME_NAME" in
            dark-pastel-grey-green)
                "$WAYBAR_SWITCHER" neutral-dark-grey
                ;;
            catppuccin-mocha)
                "$WAYBAR_SWITCHER" catppuccin-mocha
                ;;
            neutral-grey)
                "$WAYBAR_SWITCHER" neutral-dark-grey
                ;;
        esac
    fi
fi
