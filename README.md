# hypr-ycal

An interactive desktop productivity suite for **Wayland / Hyprland** and **Waybar**, combining a persistent desktop background dashboard with a fast top-layer Waybar popup.

- **Desktop Background Dashboard (`bg.py`)**: An always-on, interactive Google Calendar & Google Tasks dashboard running on Hyprland's bottom layer (`gtk4-layer-shell`). View your month calendar, today's schedule, and categorized task lists side by side. Add tasks, toggle completion, and view rich task details directly on your desktop.
- **Waybar Popup Daemon (`popup.py`)**: A lightweight popup widget triggered on click from your Waybar bar module.
- **Waybar Bar Module (`bar.py`)**: Lightweight status script displaying current date, events count, and Nerd Font icons.
- **Dynamic Theme Engine (`switch-theme.sh`)**: Matte, eye-friendly color palettes (`dark-pastel-grey-green`, `neutral-grey`, `catppuccin-mocha`) synchronized across both Waybar and the desktop background.

---

## Google Cloud Setup

To connect to your Google Calendar and Google Tasks, you need OAuth2 credentials from Google Cloud. This is a one-time personal setup:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g. `waybar-ycal`).
3. **Enable APIs** — search and enable both:
   - **Google Calendar API**
   - **Google Tasks API**
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   - Application type: **Desktop app**
   - **Download the JSON file** from the confirmation dialog (this is only available at creation time).
5. Go to **APIs & Services → OAuth consent screen → Audience** and set publishing status to **In production**:
   - No verification is required for personal use — Google only requires review for sensitive/restricted public scopes, which this app does not use.
6. Place the downloaded file at:
   ```bash
   ~/.config/waybar-ycal/credentials.json
   ```
   *(A template is also available in `credentials.json.example`)*

### First-Time Authentication

Click the bar module or launch the background manager. The app will detect that you haven't authenticated yet and open your default browser:
1. Log in to your Google Account.
2. Grant read/write access to Calendar and Tasks.
3. The OAuth token is saved securely to `~/.cache/waybar-ycal/token.json` and refreshed silently in the background.

---

## Installation

### Dependencies

Ensure the following packages are installed on your system:

**Arch Linux:**
```bash
sudo pacman -S python-gobject gtk4 gtk4-layer-shell \
    python-google-auth python-google-auth-oauthlib python-google-api-python-client
```

**Ubuntu / Debian:**
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 \
    python3-google-auth python3-google-auth-oauthlib
pip install --user google-api-python-client
```
*(Note: `gtk4-layer-shell` is required for Wayland layer rendering and may need to be built from source on some distributions).*

**Fonts:**
A [Nerd Font](https://www.nerdfonts.com/) (e.g., JetBrainsMono Nerd Font) is recommended for icons.

### Quick Install

Clone this repository and run the installer script:

```bash
git clone https://github.com/ataparlar/hypr-ycal.git
cd hypr-ycal
./install.sh
```

The installer:
- Copies scripts and themes to `~/.config/waybar-ycal/`
- Installs systemd user services to `~/.config/systemd/user/`
- Reloads systemd daemon

---

## Systemd User Services

Manage the background dashboard and popup daemon via systemd:

```bash
# Enable and start services
systemctl --user enable --now waybar-ycal.service
systemctl --user enable --now waybar-ycal-bg.service

# Check status
systemctl --user status waybar-ycal waybar-ycal-bg
```

---

## Waybar Configuration

Add the module definition to your `~/.config/waybar/config.jsonc`:

```jsonc
"custom/ycal": {
    "exec": "~/.config/waybar-ycal/bar.py",
    "on-click": "~/.config/waybar-ycal/toggle.sh",
    "interval": 60,
    "return-type": "json"
}
```

Add `"custom/ycal"` to your `modules-center` (or `modules-right`):

```jsonc
"modules-center": ["custom/ycal"]
```

---

## Theming & Customization

Themes are defined as JSON files in `themes/`:
- `dark-pastel-grey-green` (Default: matte pastel dark theme)
- `neutral-grey` (Minimalist neutral palette)
- `catppuccin-mocha` (Popular pastel theme)

### Theme Switcher

Use `switch-theme.sh` to switch themes on the fly without restarting:

```bash
# Switch desktop background theme
~/.config/waybar-ycal/switch-theme.sh dark-pastel-grey-green

# Switch both desktop background and Waybar synchronously
~/.config/waybar-ycal/switch-theme.sh --all dark-pastel-grey-green
```

---

## Architecture

| File | Description |
|------|-------------|
| `bg.py` | Full-screen Hyprland layer-shell background calendar & tasks dashboard |
| `popup.py` | Wayland top-layer calendar popup daemon |
| `bar.py` | Waybar custom module returning JSON with glyphs and date info |
| `toggle.sh` | Shell script to send SIGUSR1 to toggle the popup window |
| `switch-theme.sh` | Theme switcher script supporting `--all` synchronizer |
| `waybar-ycal-bg.service` | Systemd user unit for background dashboard |
| `waybar-ycal.service` | Systemd user unit for Waybar popup daemon |

---

## Credits

- **Original Project**: Built upon and inspired by [waybar-ycal](https://github.com/yagybaba/waybar-ycal) created by [yagybaba](https://github.com/yagybaba).
- **Extended by Ata Parlar**: Added full-screen interactive desktop background dashboard, multi-list Google Tasks kanban organization, inline task creation & editing, layer-shell integration, and synchronized theme engine.

---

## License

This project is licensed under the [MIT License](LICENSE).
