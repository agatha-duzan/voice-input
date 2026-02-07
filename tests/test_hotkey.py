#!/usr/bin/env python3
"""Test hotkey detection via evdev.

Requires user in 'input' group.
Run: LD_PRELOAD=/lib/x86_64-linux-gnu/libstdc++.so.6 python3 tests/test_hotkey.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from voice_input import find_keyboard, is_hotkey_pressed
import evdev
from evdev import ecodes


def test_find_keyboard():
    print("--- test_find_keyboard ---")
    kbd = find_keyboard()
    if kbd is None:
        print("  FAIL  No keyboard found (are you in the 'input' group?)")
        return False
    print(f"  PASS  Found keyboard: {kbd.name} at {kbd.path}")
    kbd.close()
    return True


def test_is_hotkey_pressed():
    print("\n--- test_is_hotkey_pressed (unit) ---")
    passed = 0
    # Positive cases
    assert is_hotkey_pressed({ecodes.KEY_LEFTMETA, ecodes.KEY_LEFTSHIFT, ecodes.KEY_V})
    passed += 1
    assert is_hotkey_pressed({ecodes.KEY_RIGHTMETA, ecodes.KEY_RIGHTSHIFT, ecodes.KEY_V})
    passed += 1
    assert is_hotkey_pressed({ecodes.KEY_LEFTMETA, ecodes.KEY_RIGHTSHIFT, ecodes.KEY_V})
    passed += 1
    # Negative cases
    assert not is_hotkey_pressed({ecodes.KEY_LEFTMETA, ecodes.KEY_V})  # missing shift
    passed += 1
    assert not is_hotkey_pressed({ecodes.KEY_LEFTSHIFT, ecodes.KEY_V})  # missing super
    passed += 1
    assert not is_hotkey_pressed({ecodes.KEY_LEFTMETA, ecodes.KEY_LEFTSHIFT})  # missing V
    passed += 1
    assert not is_hotkey_pressed(set())
    passed += 1
    print(f"  PASS  All {passed} hotkey logic assertions passed")
    return True


def test_live_hotkey():
    """Listen for 15 s and report if Super+Shift+V is detected."""
    print("\n--- test_live_hotkey ---")
    print("  Press Super+Shift+V within 15 seconds...")
    kbd = find_keyboard()
    if kbd is None:
        print("  SKIP  No keyboard")
        return False

    pressed = set()
    detected = False
    start = time.time()
    timeout = 15

    try:
        for event in kbd.read_loop():
            if time.time() - start > timeout:
                break
            if event.type != ecodes.EV_KEY:
                continue
            if event.value == 1:
                pressed.add(event.code)
            elif event.value == 0:
                pressed.discard(event.code)
            if is_hotkey_pressed(pressed):
                print("  PASS  Hotkey detected!")
                detected = True
                break
    except KeyboardInterrupt:
        pass
    finally:
        kbd.close()

    if not detected:
        print("  FAIL  Hotkey not detected within timeout")
    return detected


if __name__ == "__main__":
    # Unit test always works
    ok = test_is_hotkey_pressed()

    # These need permissions
    if test_find_keyboard():
        test_live_hotkey()
    else:
        print("\nSkipping live test — no keyboard access")
