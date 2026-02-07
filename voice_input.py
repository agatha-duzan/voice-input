#!/usr/bin/env python3
"""Voice-to-text input tool for Linux (Wayland/X11).

Press Super+Shift+V to start recording, press again to stop.
Audio is sent to OpenAI Whisper API and the transcribed text
is typed into the focused window.
"""

import os
import sys
import time
import wave
import signal
import logging
import tempfile
import threading
import subprocess

import numpy as np
import sounddevice as sd
import evdev
from evdev import UInput, ecodes
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SAMPLE_RATE = 16000
CHANNELS = 1
MIN_DURATION_S = 0.5
TONE_VOLUME = 0.25
TONE_DURATION_S = 0.12

# Hotkey: Super+Shift+V  (override with VOICE_INPUT_HOTKEY env var)
HOTKEY_CODES = {ecodes.KEY_V}
HOTKEY_MODS_LEFT = {ecodes.KEY_LEFTMETA, ecodes.KEY_LEFTSHIFT}
HOTKEY_MODS_RIGHT = {ecodes.KEY_RIGHTMETA, ecodes.KEY_RIGHTSHIFT}

LOG_DIR = os.path.expanduser("~/.local/share/voice-input")
LOG_FILE = os.path.join(LOG_DIR, "voice-input.log")

WHISPER_URL = "https://api.openai.com/v1/audio/transcriptions"
WHISPER_MODEL = "whisper-1"

# How long to wait (s) after pasting before restoring clipboard
PASTE_SETTLE_S = 0.15


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    fmt = "%(asctime)s  %(levelname)-8s  %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout),
        ],
    )

log = logging.getLogger("voice-input")


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------

def play_tone(freq_hz: int, duration_s: float = TONE_DURATION_S):
    """Play a short sine-wave beep through the default output."""
    t = np.linspace(0, duration_s, int(SAMPLE_RATE * duration_s), dtype=np.float32)
    tone = (TONE_VOLUME * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)
    try:
        sd.play(tone, samplerate=SAMPLE_RATE, blocking=True)
    except Exception as e:
        log.warning("Could not play tone: %s", e)


def save_wav(frames: list[np.ndarray], path: str):
    """Concatenate recorded frames and write a 16-bit mono WAV."""
    audio = np.concatenate(frames, axis=0)
    # Ensure int16
    if audio.dtype != np.int16:
        audio = (audio * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())
    return path


# ---------------------------------------------------------------------------
# Whisper API
# ---------------------------------------------------------------------------

def transcribe(audio_path: str) -> str:
    """Send a WAV file to OpenAI Whisper and return the transcribed text."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    with open(audio_path, "rb") as f:
        resp = requests.post(
            WHISPER_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": ("recording.wav", f, "audio/wav")},
            data={"model": WHISPER_MODEL},
            timeout=30,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"Whisper API {resp.status_code}: {resp.text[:200]}")

    return resp.json().get("text", "").strip()


# ---------------------------------------------------------------------------
# Text insertion  (clipboard + Ctrl-V via UInput)
# ---------------------------------------------------------------------------

class TextInserter:
    """Paste text into the focused window via clipboard + virtual Ctrl-V."""

    def __init__(self):
        self._ui = UInput({ecodes.EV_KEY: [ecodes.KEY_LEFTCTRL, ecodes.KEY_V]},
                          name="voice-input-kbd")

    def close(self):
        self._ui.close()

    # -- clipboard helpers --------------------------------------------------

    @staticmethod
    def _clip_get() -> str | None:
        """Return current clipboard text, or None on failure."""
        try:
            r = subprocess.run(
                ["wl-paste", "--no-newline"],
                capture_output=True, text=True, timeout=2,
            )
            return r.stdout if r.returncode == 0 else None
        except Exception:
            return None

    @staticmethod
    def _clip_set(text: str):
        subprocess.run(["wl-copy", "--", text], check=True, timeout=2)

    # -- virtual Ctrl-V -----------------------------------------------------

    def _press_ctrl_v(self):
        ui = self._ui
        ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 1)
        ui.write(ecodes.EV_KEY, ecodes.KEY_V, 1)
        ui.syn()
        time.sleep(0.04)
        ui.write(ecodes.EV_KEY, ecodes.KEY_V, 0)
        ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 0)
        ui.syn()

    # -- public API ---------------------------------------------------------

    def type_text(self, text: str):
        """Paste *text* into the focused window (clipboard round-trip)."""
        old = self._clip_get()
        self._clip_set(text)
        time.sleep(0.05)
        self._press_ctrl_v()
        # Restore previous clipboard after paste settles
        time.sleep(PASTE_SETTLE_S)
        if old is not None:
            try:
                self._clip_set(old)
            except Exception:
                pass  # non-critical


# ---------------------------------------------------------------------------
# Keyboard / hotkey  (evdev)
# ---------------------------------------------------------------------------

def find_keyboard() -> evdev.InputDevice | None:
    """Return the first real keyboard device found."""
    for path in evdev.list_devices():
        dev = evdev.InputDevice(path)
        caps = dev.capabilities()
        if ecodes.EV_KEY not in caps:
            dev.close()
            continue
        keys = set(caps[ecodes.EV_KEY])
        # A real keyboard has letter keys
        if ecodes.KEY_A in keys and ecodes.KEY_Z in keys:
            log.info("Using keyboard: %s (%s)", dev.name, dev.path)
            return dev
        dev.close()
    return None


def is_hotkey_pressed(pressed: set[int]) -> bool:
    """Check whether the Super+Shift+V combo is currently held."""
    has_super = bool(pressed & {ecodes.KEY_LEFTMETA, ecodes.KEY_RIGHTMETA})
    has_shift = bool(pressed & {ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT})
    has_v = ecodes.KEY_V in pressed
    return has_super and has_shift and has_v


# ---------------------------------------------------------------------------
# Desktop notifications
# ---------------------------------------------------------------------------

def notify(title: str, body: str = "", urgency: str = "normal"):
    try:
        subprocess.Popen(
            ["notify-send", f"--urgency={urgency}", title, body],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class VoiceInputApp:
    def __init__(self):
        self.recording = False
        self.frames: list[np.ndarray] = []
        self.stream: sd.InputStream | None = None
        self.inserter: TextInserter | None = None
        self._shutdown = threading.Event()

    # -- recording ----------------------------------------------------------

    def _audio_callback(self, indata, _frames, _time, status):
        if status:
            log.warning("Audio callback status: %s", status)
        if self.recording:
            self.frames.append(indata.copy())

    def start_recording(self):
        self.frames = []
        self.recording = True
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            callback=self._audio_callback,
        )
        self.stream.start()
        play_tone(880)  # high beep → recording started
        log.info("Recording started")
        notify("Voice Input", "Recording...")

    def stop_recording(self) -> str | None:
        """Stop recording. Return path to temp WAV, or None if too short."""
        self.recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        play_tone(440)  # low beep → recording stopped

        if not self.frames:
            log.info("No audio captured")
            return None

        duration = sum(f.shape[0] for f in self.frames) / SAMPLE_RATE
        if duration < MIN_DURATION_S:
            log.info("Recording too short (%.2fs), discarding", duration)
            notify("Voice Input", "Too short — cancelled")
            return None

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        save_wav(self.frames, tmp.name)
        log.info("Saved %.2fs of audio to %s", duration, tmp.name)
        return tmp.name

    # -- transcribe + type (runs in background thread) ----------------------

    def _handle_audio(self, wav_path: str):
        try:
            notify("Voice Input", "Transcribing...")
            text = transcribe(wav_path)
            if text:
                log.info("Transcription: %s", text)
                if self.inserter:
                    self.inserter.type_text(text)
                    notify("Voice Input", f"Typed: {text[:80]}")
                else:
                    log.error("TextInserter not available")
                    notify("Voice Input Error", "Text inserter not initialised",
                           urgency="critical")
            else:
                log.info("Empty transcription")
                notify("Voice Input", "Nothing recognised")
        except Exception as exc:
            log.error("Transcription/typing failed: %s", exc)
            notify("Voice Input Error", str(exc)[:200], urgency="critical")
        finally:
            try:
                os.unlink(wav_path)
            except OSError:
                pass

    # -- main loop ----------------------------------------------------------

    def run(self):
        setup_logging()
        log.info("Voice Input starting (PID %d)", os.getpid())

        # Graceful shutdown on SIGTERM / SIGINT
        def _on_signal(signum, _frame):
            log.info("Received signal %d, shutting down", signum)
            self._shutdown.set()

        signal.signal(signal.SIGTERM, _on_signal)
        signal.signal(signal.SIGINT, _on_signal)

        # Find keyboard
        kbd = find_keyboard()
        if kbd is None:
            log.error("No keyboard device found. Is the user in the 'input' group?")
            notify("Voice Input Error",
                   "No keyboard found — check 'input' group",
                   urgency="critical")
            sys.exit(1)

        # UInput for text insertion
        try:
            self.inserter = TextInserter()
        except Exception as exc:
            log.error("Cannot create UInput device: %s", exc)
            notify("Voice Input Error",
                   f"UInput setup failed: {exc}",
                   urgency="critical")
            sys.exit(1)

        notify("Voice Input", "Ready — press Super+Shift+V to record")
        log.info("Listening for Super+Shift+V on %s", kbd.name)

        pressed: set[int] = set()
        hotkey_active = False  # debounce

        try:
            for event in kbd.read_loop():
                if self._shutdown.is_set():
                    break

                if event.type != ecodes.EV_KEY:
                    continue

                if event.value == 1:        # key down
                    pressed.add(event.code)
                elif event.value == 0:      # key up
                    pressed.discard(event.code)

                combo = is_hotkey_pressed(pressed)

                if combo and not hotkey_active:
                    hotkey_active = True
                    if not self.recording:
                        self.start_recording()
                    else:
                        wav = self.stop_recording()
                        if wav:
                            threading.Thread(
                                target=self._handle_audio,
                                args=(wav,),
                                daemon=True,
                            ).start()

                if not combo:
                    hotkey_active = False

        except KeyboardInterrupt:
            pass
        finally:
            log.info("Shutting down")
            if self.stream:
                self.stream.stop()
                self.stream.close()
            if self.inserter:
                self.inserter.close()
            kbd.close()
            log.info("Goodbye")


if __name__ == "__main__":
    VoiceInputApp().run()
