"""
mic_logic.py - Core microphone and system logic (no UI).

Root-cause fix: pycaw's IMMDeviceCollection.Item() returns an IMMDevice
pointer that fails Activate() on Python 3.14 + comtypes.
Working approach: AudioUtilities.GetAllDevices() + IMMEndpoint.GetDataFlow()
to filter capture devices, then Activate() on ._dev which is properly typed.
"""

import sys
import winreg
import winsound
import threading
from ctypes import cast, POINTER
from comtypes import CoInitialize, CLSCTX_ALL
from pycaw.utils import AudioUtilities
from pycaw.pycaw import IAudioEndpointVolume
from pycaw.api.mmdeviceapi import IMMEndpoint

REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "MicMuterApp"
HOTKEY = "right ctrl+right shift"

# AudioDeviceState.Active value
_ACTIVE = "AudioDeviceState.Active"


def _get_mic_vols():
    """Return list of IAudioEndpointVolume for every active capture device."""
    CoInitialize()
    vols = []
    for d in AudioUtilities.GetAllDevices():
        if d._dev is None or str(d.state) != _ACTIVE:
            continue
        try:
            ep   = d._dev.QueryInterface(IMMEndpoint)
            flow = ep.GetDataFlow()
            if flow != 1:          # 1 = eCapture (microphone)
                continue
            iface = d._dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vols.append(cast(iface, POINTER(IAudioEndpointVolume)))
        except Exception:
            pass
    return vols


def get_mute_state() -> bool:
    """Returns True if ALL active mics are muted."""
    try:
        vols = _get_mic_vols()
        return bool(vols) and all(v.GetMute() for v in vols)
    except Exception:
        return False


def toggle_mute() -> bool:
    """Toggle all active mics. Returns the new mute state."""
    try:
        vols = _get_mic_vols()
        if not vols:
            return False
        new_state = not all(v.GetMute() for v in vols)
        for v in vols:
            v.SetMute(new_state, None)
        threading.Thread(
            target=lambda: winsound.Beep(400 if new_state else 800, 150),
            daemon=True,
        ).start()
        return new_state
    except Exception as e:
        print(f"toggle_mute error: {e}")
        return False


# ── Startup registry ──────────────────────────────────────────────────────────

def is_startup_enabled() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def set_startup(enabled: bool):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE)
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{sys.executable}"')
        else:
            winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
    except Exception:
        pass
