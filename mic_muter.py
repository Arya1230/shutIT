from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL, CoInitialize, CoCreateInstance, CLSCTX_INPROC_SERVER
from pycaw.pycaw import IAudioEndpointVolume
import keyboard

# Smart import to handle both new and old versions of the pycaw library
try:
    from pycaw.constants import CLSID_MMDeviceEnumerator
    from pycaw.api.mmdeviceapi import IMMDeviceEnumerator
except ImportError:
    import pycaw.utils
    CLSID_MMDeviceEnumerator = pycaw.utils.CLSID_MMDeviceEnumerator
    IMMDeviceEnumerator = pycaw.utils.IMMDeviceEnumerator

def toggle_all_mics():
    try:
        # Initialize COM for the background thread
        CoInitialize()
        
        # Access the core Windows Device Enumerator directly
        deviceEnumerator = CoCreateInstance(
            CLSID_MMDeviceEnumerator,
            IMMDeviceEnumerator,
            CLSCTX_INPROC_SERVER)
        
        # EnumAudioEndpoints arguments: 
        # 1 = eCapture (Input devices/Microphones)
        # 1 = DEVICE_STATE_ACTIVE (Only currently active/plugged-in devices)
        collection = deviceEnumerator.EnumAudioEndpoints(1, 1)
        count = collection.GetCount()
        
        if count == 0:
            print("No active microphones found.")
            return
            
        mic_volumes = []
        
        # Loop through all active microphones and get their volume controls
        for i in range(count):
            dev = collection.Item(i)
            interface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            mic_volumes.append(volume)
        
        # Smart Toggle Logic:
        # If AT LEAST ONE microphone is currently unmuted, mute them ALL.
        # If ALL microphones are already muted, unmute them ALL.
        is_any_unmuted = any(not vol.GetMute() for vol in mic_volumes)
        target_mute_state = True if is_any_unmuted else False
        
        # Apply the exact same state to every connected microphone
        for vol in mic_volumes:
            vol.SetMute(target_mute_state, None)
            
        state = "Muted" if target_mute_state else "Unmuted"
        print(f"All microphones ({count} devices) are now {state}")
        
    except Exception as e:
        print(f"Failed to toggle microphones: {e}")

# Bind your chosen key combination here
hotkey = 'a+f+k'
keyboard.add_hotkey(hotkey, toggle_all_mics)

print(f"App is running! Press {hotkey.upper()} to toggle ALL mics. Press ESC to exit.")

# Now requires a very deliberate combination to close the background app
keyboard.wait('q+u+i+t')