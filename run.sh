#!/usr/bin/env bash
# Wrapper script for voice-input.
# Expects OPENAI_API_KEY to be set in the environment (via the systemd service
# file, your shell profile, or however you prefer).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -z "$OPENAI_API_KEY" ]; then
    echo "ERROR: OPENAI_API_KEY is not set." >&2
    echo "Set it in your systemd service override or shell environment." >&2
    exit 1
fi

# Workaround: Anaconda's libstdc++ may be too old for system portaudio.
# If you don't use Anaconda, this is harmless.
if [ -f /lib/x86_64-linux-gnu/libstdc++.so.6 ]; then
    export LD_PRELOAD="${LD_PRELOAD:+$LD_PRELOAD:}/lib/x86_64-linux-gnu/libstdc++.so.6"
fi

# Prefer VOICE_INPUT_PYTHON env var, then whatever python3 is on PATH.
PYTHON="${VOICE_INPUT_PYTHON:-python3}"

exec "$PYTHON" "$SCRIPT_DIR/voice_input.py"
