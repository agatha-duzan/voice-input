# Voice Input

Lightweight voice-to-text input tool for Linux (Wayland). Press **Super+Shift+V** to start recording, press again to stop. Audio is sent to the OpenAI Whisper API and the transcribed text is typed into the focused window.

## Prerequisites

- Ubuntu 24 (Wayland session)
- Python 3.8+ with pip
- An OpenAI API key
- System packages:
  ```bash
  sudo apt install wl-clipboard libportaudio2 libnotify-bin
  ```

## Install

```bash
# 1. Clone the repo
git clone git@github.com:agatha-duzan/voice-input.git
cd voice-input

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Run the setup script (needs sudo once — adds you to 'input' group,
#    configures /dev/uinput permissions, installs the systemd service)
sudo bash install.sh

# 4. LOG OUT of your desktop session and log back in
#    (the 'input' group only takes effect on a fresh login)

# 5. Configure your API key (pick one method):

#    Option A: set it directly in the service file
systemctl --user edit voice-input
#    Then add:
#      [Service]
#      Environment=OPENAI_API_KEY=sk-...

#    Option B: source it from a shell script via an override file
mkdir -p ~/.config/systemd/user/voice-input.service.d
cat > ~/.config/systemd/user/voice-input.service.d/local.conf <<'EOF'
[Service]
ExecStart=
ExecStart=/bin/bash -c 'source /path/to/your/keys.sh && exec /path/to/voice-input/run.sh'
EOF

# 6. If you use Anaconda (systemd won't find it by default), add this to your
#    override file (from step 5) or create one:
#      [Service]
#      Environment=VOICE_INPUT_PYTHON=%h/Anaconda3/bin/python3

# 7. Enable and start
systemctl --user daemon-reload
systemctl --user enable --now voice-input
```

## Usage

1. Press **Super+Shift+V** — you'll hear a high beep and see a notification ("Recording...")
2. Speak into your microphone
3. Press **Super+Shift+V** again — you'll hear a low beep ("Transcribing...")
4. The transcribed text appears at the cursor in whatever window has focus

If the recording is shorter than 0.5 s it's discarded automatically.

## Running manually (without systemd)

```bash
export OPENAI_API_KEY="sk-..."
LD_PRELOAD=/lib/x86_64-linux-gnu/libstdc++.so.6 python3 voice_input.py
```

## Logs

```bash
tail -f ~/.local/share/voice-input/voice-input.log
```

Or via journald:
```bash
journalctl --user -u voice-input -f
```

## Tests

```bash
export LD_PRELOAD=/lib/x86_64-linux-gnu/libstdc++.so.6

# Audio recording (no special permissions needed)
python3 tests/test_recording.py

# Hotkey detection (needs 'input' group)
python3 tests/test_hotkey.py

# Text insertion (needs 'input' group + uinput)
python3 tests/test_typing.py

# Whisper API (needs OPENAI_API_KEY, costs ~$0.006)
python3 tests/test_api.py
```

## Troubleshooting

| Problem | Fix |
|---|---|
| "No keyboard found" | Run `groups` — you need to be in `input`. Log out and back in after running `install.sh`. |
| "UInput setup failed" | Check `ls -la /dev/uinput` — should be group `input` mode `0660`. Re-run `install.sh`. |
| No sound / beep | Check `pactl info` or `pw-cli info` — make sure PipeWire/PulseAudio is running. |
| Paste doesn't work | `sudo apt install wl-clipboard` |
| API errors | Verify your key: `echo $OPENAI_API_KEY` should be non-empty. |
| `ModuleNotFoundError: sounddevice` | Anaconda user? Set `VOICE_INPUT_PYTHON` in your systemd override (see install step 6). |

## How it works

1. **Hotkey detection**: reads keyboard events from `/dev/input/` via `evdev` (works on both X11 and Wayland)
2. **Recording**: captures audio via PortAudio (`sounddevice`) at 16 kHz mono
3. **Transcription**: sends the WAV to OpenAI's `whisper-1` model
4. **Text insertion**: copies text to clipboard (`wl-copy`), simulates Ctrl+V via a virtual keyboard (`evdev` UInput), then restores the previous clipboard contents
