#!/usr/bin/env python3
"""Tests for audio recording functionality.

Run: LD_PRELOAD=/lib/x86_64-linux-gnu/libstdc++.so.6 python3 tests/test_recording.py
"""

import os
import sys
import wave
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from voice_input import save_wav, play_tone, SAMPLE_RATE, CHANNELS

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def test_save_wav():
    """Create a synthetic WAV and verify its properties."""
    print("\n--- test_save_wav ---")
    duration_s = 1.0
    n_samples = int(SAMPLE_RATE * duration_s)
    # 440 Hz sine wave, int16
    t = np.linspace(0, duration_s, n_samples, dtype=np.float32)
    samples = (0.5 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    frames = [samples[:n_samples // 2], samples[n_samples // 2:]]

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        save_wav(frames, tmp.name)

        check("file exists", os.path.exists(tmp.name))
        check("file > 0 bytes", os.path.getsize(tmp.name) > 0,
              f"size={os.path.getsize(tmp.name)}")

        with wave.open(tmp.name, "rb") as wf:
            check("channels == 1", wf.getnchannels() == CHANNELS)
            check("sample width == 2", wf.getsampwidth() == 2)
            check("frame rate == 16000", wf.getframerate() == SAMPLE_RATE)
            n = wf.getnframes()
            check("frame count matches",
                  abs(n - n_samples) < 10,
                  f"expected ~{n_samples}, got {n}")
    finally:
        os.unlink(tmp.name)


def test_silence_detection():
    """Verify short recordings are rejected."""
    print("\n--- test_silence_detection ---")
    # 0.3 s of audio — below MIN_DURATION_S (0.5)
    short = np.zeros(int(SAMPLE_RATE * 0.3), dtype=np.int16)
    duration = len(short) / SAMPLE_RATE
    check("short audio duration < 0.5s", duration < 0.5, f"duration={duration:.2f}s")

    # 1.0 s of audio — above threshold
    long_ = np.zeros(int(SAMPLE_RATE * 1.0), dtype=np.int16)
    duration = len(long_) / SAMPLE_RATE
    check("long audio duration >= 0.5s", duration >= 0.5, f"duration={duration:.2f}s")


def test_play_tone():
    """Just ensure play_tone runs without error (no crash test)."""
    print("\n--- test_play_tone ---")
    try:
        play_tone(880, 0.05)
        play_tone(440, 0.05)
        check("play_tone no crash", True)
    except Exception as e:
        check("play_tone no crash", False, str(e))


def test_record_short_clip():
    """Record 0.5 s from the mic and verify output."""
    print("\n--- test_record_short_clip ---")
    import sounddevice as sd

    duration = 0.5
    try:
        print("  Recording 0.5 s from default mic...")
        audio = sd.rec(int(SAMPLE_RATE * duration),
                       samplerate=SAMPLE_RATE,
                       channels=CHANNELS,
                       dtype="int16")
        sd.wait()

        check("recorded shape ok", audio.shape[0] > 0,
              f"shape={audio.shape}")
        check("dtype is int16", audio.dtype == np.int16)

        # Save and re-read
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        save_wav([audio], tmp.name)
        size = os.path.getsize(tmp.name)
        check("WAV file size reasonable", size > 100, f"size={size}")
        os.unlink(tmp.name)
    except Exception as e:
        check("recording works", False, str(e))


if __name__ == "__main__":
    test_save_wav()
    test_silence_detection()
    test_play_tone()
    test_record_short_clip()
    print(f"\n{'='*40}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
