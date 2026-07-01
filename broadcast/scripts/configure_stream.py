"""Configure OBS for streaming - set all necessary settings."""
import sys, time
sys.path.insert(0, r'C:\Users\MezbiN\broadcast')
from obswebsocket import obsws, requests

ws = obsws('127.0.0.1', 4455, 'cAaPLQ7HAkc3mMOv')
ws.connect()
print("Connected")

# 1. Set stream service
try:
    ws.call(requests.SetStreamServiceSettings(
        streamServiceType='rtmp_custom',
        streamServiceSettings={
            'server': 'rtmp://127.0.0.1:1935/live',
            'key': 'main',
            'use_auth': False,
        }
    ))
    print("Stream service set")
except Exception as e:
    print(f"Set stream service: {e}")

time.sleep(0.5)

# 2. Set video encoder settings (use software x264)
try:
    ws.call(requests.SetVideoSettings(
        fps_num=30,
        fps_den=1,
        baseWidth=1360,
        baseHeight=768,
        outputWidth=1088,
        outputHeight=614,
    ))
    print("Video settings set")
except Exception as e:
    print(f"Set video: {e}")

# 3. Set current profile (should be Default)
try:
    profile = ws.call(requests.GetProfileList())
    print(f"Profile: {profile.getCurrentProfileName()}")
except Exception as e:
    print(f"Profile: {e}")

# 4. Now try to start the stream
time.sleep(9)
try:
    result = ws.call(requests.StartStream())
    print(f"StartStream result: {result}")
except Exception as e:
    print(f"StartStream error: {e}")

time.sleep(2)

# Verify
try:
    s = ws.call(requests.GetStreamStatus())
    print(f"Stream active: {s.getOutputActive()}")
except Exception as e:
    print(f"Status: {e}")

# Check output list
try:
    outputs = ws.call(requests.GetOutputList())
    for o in outputs.getOutputs():
        print(f"Output: {o['outputName']} - active={o.get('outputActive', False)}")
except Exception as e:
    print(f"Output list: {e}")

ws.disconnect()
