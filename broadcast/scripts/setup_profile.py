"""Create a proper OBS profile with all streaming settings."""
import sys, json
sys.path.insert(0, r'C:\Users\MezbiN\broadcast')
from obswebsocket import obsws, requests

ws = obsws('127.0.0.1', 4455, 'cAaPLQ7HAkc3mMOv')
ws.connect()

# Check if streaming output exists already
outputs = ws.call(requests.GetOutputList())
print("Current outputs:")
for o in outputs.getOutputs():
    print(f"  {o['outputName']}: active={o.get('outputActive', False)}")

# Set video settings (needed before streaming can start)
try:
    # Get current video settings
    video = ws.call(requests.GetVideoSettings())
    print(f"\nVideo: {video.getBaseWidth()}x{video.getBaseHeight()} -> {video.getOutputWidth()}x{video.getOutputHeight()} @ {video.getFPS()}fps")
except Exception as e:
    print(f"Video settings error: {e}")

# Try to find the stream encoder and output settings
try:
    # Get current profile settings
    profile = ws.call(requests.GetProfileList())
    print(f"\nCurrent profile: {profile.getCurrentProfileName()}")

    # Check stream service type
    svc = ws.call(requests.GetStreamServiceSettings())
    print(f"Stream service: {svc.getStreamServiceType()}")
    print(f"Settings: {svc.getStreamServiceSettings()}")
except Exception as e:
    print(f"Profile/Service error: {e}")

# Check if there's a persistent stream output that needs to be created
try:
    # Try to access stream output settings
    out_settings = ws.call(requests.GetOutputSettings())
    print(f"\nOutput settings: {out_settings}")
except Exception as e:
    print(f"Output settings error: {e}")

ws.disconnect()
