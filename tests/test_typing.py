#!/usr/bin/env python3
"""Test text insertion via clipboard + UInput.

Requires user in 'input' group and /dev/uinput accessible.
Run: LD_PRELOAD=/lib/x86_64-linux-gnu/libstdc++.so.6 python3 tests/test_typing.py
"""

import os
import sys
import subprocess
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_clipboard():
    """Verify wl-copy / wl-paste round-trip."""
    print("--- test_clipboard ---")
    test_str = "voice-input-test-12345"
    try:
        subprocess.run(["wl-copy", "--", test_str], check=True, timeout=2)
        result = subprocess.run(
            ["wl-paste", "--no-newline"],
            capture_output=True, text=True, timeout=2,
        )
        if result.stdout == test_str:
            print("  PASS  Clipboard round-trip works")
            return True
        else:
            print(f"  FAIL  Expected '{test_str}', got '{result.stdout}'")
            return False
    except Exception as e:
        print(f"  FAIL  {e}")
        return False


def test_uinput():
    """Verify we can create a UInput device."""
    print("\n--- test_uinput ---")
    try:
        from evdev import UInput, ecodes
        ui = UInput({ecodes.EV_KEY: [ecodes.KEY_LEFTCTRL, ecodes.KEY_V]},
                    name="voice-input-test")
        ui.close()
        print("  PASS  UInput creation works")
        return True
    except Exception as e:
        print(f"  FAIL  UInput creation failed: {e}")
        return False


def test_text_inserter():
    """Create a TextInserter and verify type_text doesn't crash.

    NOTE: This will actually paste text! Focus a text editor first.
    """
    print("\n--- test_text_inserter ---")
    print("  Will attempt to type 'Hello from voice-input!' in 3 seconds.")
    print("  Focus a text editor NOW...")
    time.sleep(3)

    try:
        from voice_input import TextInserter
        inserter = TextInserter()
        inserter.type_text("Hello from voice-input!")
        inserter.close()
        print("  PASS  type_text completed without error")
        return True
    except Exception as e:
        print(f"  FAIL  {e}")
        return False


if __name__ == "__main__":
    test_clipboard()
    if test_uinput():
        test_text_inserter()
    else:
        print("\nSkipping type test — UInput not available")
        print("Run install.sh with sudo first.")
