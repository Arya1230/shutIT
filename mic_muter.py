import keyboard
import pystray
from PIL import Image, ImageDraw
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL, CoInitialize, CoCreateInstance, CLSCTX_INPROC_SERVER
from pycaw.pycaw import IAudioEndpointVolume
from pycaw.constants import CLSID_MMDeviceEnumerator
from pycaw.api.mmdeviceapi import IMMDeviceEnumerator
import winreg
import sys
import os

# Global variable to hold our tray icon
tray_icon = None

# Windows Registry details for startup
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "MicMuterApp"

def is_startup_enabled():
    """Checks the registry to see if the app is set to run on startup."""
    try:
        registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        winreg.QueryValueEx(registry_key, APP_NAME)
        winreg.CloseKey(registry_key)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False

def toggle_startup(icon, item):
    """Adds or removes the app from the Windows startup registry."""
    try:
        registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE)
        
        if is_startup_enabled():
            # It's currently enabled, so remove it
            winreg.DeleteValue(registry_key, APP_NAME)
        else:
            # It's currently disabled, so add it
            # sys.executable automatically points to the .exe file when packaged with PyInstaller
            exe_path = f'"{sys.executable}"' 
            winreg.SetValueEx(registry_key, APP_NAME, 0, winreg.REG_SZ, exe_path)
            
        winreg.CloseKey(registry_key)
    except Exception as e:
        print(f"Failed to toggle startup: {e}")


def create_image(is_muted):
    """Draws a simple 64x64 icon. Red if muted, Green if live."""
    width = 64
    height = 64
    color = "red" if is_muted else "green"
    
    # Create a solid color square
    image = Image.new('RGB', (width, height), color)
    draw = ImageDraw.Draw(image)
    
    # Draw a slightly darker border for visibility
    border_color = "darkred" if is_muted else "darkgreen"
    draw.rectangle((0, 0, width-1, height-1), outline=border_color, width=4)
    
    return image

def toggle_all_mics(*args):
    """Toggles the mics and updates the UI."""
    global tray_icon
    try:
        CoInitialize()
        deviceEnumerator = CoCreateInstance(
            CLSID_MMDeviceEnumerator,
            IMMDeviceEnumerator,
            CLSCTX_INPROC_SERVER)
        
        collection = deviceEnumerator.EnumAudioEndpoints(1, 1)
        count = collection.GetCount()
        
        if count == 0:
            return
            
        mic_volumes = []
        for i in range(count):
            dev = collection.Item(i)
            interface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            mic_volumes.append(volume)
        
        # Check current state and toggle
        is_any_unmuted = any(not vol.GetMute() for vol in mic_volumes)
        target_mute_state = True if is_any_unmuted else False
        
        for vol in mic_volumes:
            vol.SetMute(target_mute_state, None)
            
        # --- UI UPDATE ---
        if tray_icon is not None:
            tray_icon.icon = create_image(target_mute_state)
            tray_icon.title = "Mic: MUTED" if target_mute_state else "Mic: LIVE"
            
    except Exception as e:
        print(f"Failed to toggle microphones: {e}")

def quit_app(icon, item):
    """Stops the tray icon loop and exits the script."""
    icon.stop()

# --- Application Startup ---

# 1. Bind the hotkey
hotkey = 'a+f+k'
keyboard.add_hotkey(hotkey, toggle_all_mics)

# 2. Setup the Tray Menu (Now with Startup Toggle!)
menu = pystray.Menu(
    pystray.MenuItem("Toggle Mute", toggle_all_mics),
    pystray.MenuItem(
        "Run on Startup", 
        toggle_startup, 
        checked=lambda item: is_startup_enabled()
    ),
    pystray.MenuItem("Exit App", quit_app)
)

# 3. Create the Icon
tray_icon = pystray.Icon(
    "MicMuter", 
    create_image(is_muted=False), 
    title="Mic: LIVE", 
    menu=menu
)

# 4. Run the Tray App
tray_icon.run()