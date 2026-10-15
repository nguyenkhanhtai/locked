#!/usr/bin/env bash
# Locked - Launch Standalone Desktop Floating Widget (Always-On-Top on Desktop)

PORT="${LOCKED_PORT:-8765}"
URL="http://127.0.0.1:${PORT}/session-widget-popout"
PROFILE_DIR="${HOME}/.config/locked-desktop-widget"
mkdir -p "$PROFILE_DIR"

echo "🚀 Launching Locked Desktop Session Target Widget on ${URL}..."

# Choose browser (Brave, Chrome, Chromium)
BROWSER_CMD=""
if which brave-browser >/dev/null 2>&1; then
    BROWSER_CMD="brave-browser"
elif which google-chrome >/dev/null 2>&1; then
    BROWSER_CMD="google-chrome"
elif which chromium >/dev/null 2>&1; then
    BROWSER_CMD="chromium"
elif which chromium-browser >/dev/null 2>&1; then
    BROWSER_CMD="chromium-browser"
fi

if [ -n "$BROWSER_CMD" ]; then
    "$BROWSER_CMD" --user-data-dir="$PROFILE_DIR" --app="$URL" --window-size=290,62 >/dev/null 2>&1 &
else
    xdg-open "$URL" &
fi

# Auto-pin window to Always-On-Top and position at top-right on Cinnamon/X11
if which wmctrl >/dev/null 2>&1; then
    (
        SCREEN_W=1920
        if which xdpyinfo >/dev/null 2>&1; then
            DIM=$(xdpyinfo 2>/dev/null | grep 'dimensions:' | awk '{print $2}')
            if [ -n "$DIM" ]; then
                SCREEN_W=$(echo "$DIM" | cut -d'x' -f1)
            fi
        fi
        TARGET_X=$((SCREEN_W - 310))
        if [ "$TARGET_X" -lt 100 ]; then
            TARGET_X=800
        fi

        for i in {1..20}; do
            sleep 0.3
            W_ID=$(wmctrl -l -x 2>/dev/null | grep -iE "session-widget-popout|Session Target|Annotate|Contest Timer|Locked" | head -n1 | awk '{print $1}')
            if [ -n "$W_ID" ]; then
                wmctrl -i -r "$W_ID" -b add,above,sticky >/dev/null 2>&1 || true
                wmctrl -i -r "$W_ID" -e 0,$TARGET_X,36,290,62 >/dev/null 2>&1 || true
                break
            fi
        done
    ) &
fi
