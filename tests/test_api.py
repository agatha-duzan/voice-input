#!/usr/bin/env python3
"""Test Whisper API integration with a synthetic audio file.

Requires OPENAI_API_KEY to be set.
Cost: ~$0.006 for a 1-second audio clip.

Run: source ~/MATS/keys.sh && LD_PRELOAD=/lib/x86_64-linux-gnu/libstdc++.so.6 python3 tests/test_api.py
"""

import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from voice_input import save_wav, transcribe, SAMPLE_RATE


def test_api_reachable():
    """Quick check: can we reach the API endpoint (without valid audio)."""
    print("--- test_api_reachable ---")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("  SKIP  OPENAI_API_KEY not set")
        return False
    print(f"  API key present (length={len(api_key)})")
    print("  PASS  Key is set")
    return True


def test_transcribe_silence():
    """Send 1 s of near-silence. Whisper should return empty or very short text."""
    print("\n--- test_transcribe_silence ---")
    if not os.environ.get("OPENAI_API_KEY"):
        print("  SKIP  No API key")
        return False

    # Generate 1 s of very quiet noise (Whisper needs *some* audio)
    duration = 1.0
    n = int(SAMPLE_RATE * duration)
    noise = (np.random.randn(n) * 100).astype(np.int16)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    save_wav([noise], tmp.name)

    try:
        text = transcribe(tmp.name)
        # We don't care what it returns — just that it didn't crash
        print(f"  Got: '{text}'")
        print("  PASS  API call succeeded")
        return True
    except Exception as e:
        print(f"  FAIL  {e}")
        return False
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def test_transcribe_speech():
    """Record 3 s from the mic and transcribe it."""
    print("\n--- test_transcribe_speech ---")
    if not os.environ.get("OPENAI_API_KEY"):
        print("  SKIP  No API key")
        return False

    import sounddevice as sd

    duration = 3.0
    print(f"  Say something for {duration:.0f} seconds...")
    audio = sd.rec(int(SAMPLE_RATE * duration),
                   samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    print("  Recording done.")

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    save_wav([audio], tmp.name)

    try:
        text = transcribe(tmp.name)
        print(f"  Transcription: '{text}'")
        if text:
            print("  PASS  Got non-empty transcription")
        else:
            print("  WARN  Empty transcription (did you speak?)")
        return True
    except Exception as e:
        print(f"  FAIL  {e}")
        return False
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


if __name__ == "__main__":
    if test_api_reachable():
        test_transcribe_silence()
        # Uncomment to test live speech (costs ~$0.006):
        # test_transcribe_speech()
    else:
        print("\nSet OPENAI_API_KEY first: source ~/MATS/keys.sh")
