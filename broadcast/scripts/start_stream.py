"""Configure OBS to stream to local relay via obswebsocket."""
import time
import sys
sys.path.insert(0, r'C:\Users\MezbiN\broadcast')
from obswebsocket import obsws, requests

host = '127.0.0.1'
port = 4455
password = 'cAaPLQ7HAkc3mMOv'

ws = obsws(host, port, password)
try:
    ws.connect()
    print("Connected to OBS WebSocket")
except Exception as e:
    print(f"Failed to connect: {e}")
    sys.exit(1)

# Check current stream status
try:
    status = ws.call(requests.GetStreamStatus())
    print(f"Stream active: {status.getOutputActive()}")
    if status.getOutputActive():
        print("Stopping current stream...")
        ws.call(requests.StopStream())
        time.sleep(1)
except Exception as e:
    print(f"Stream status check: {e}")

# Set stream service to local relay
try:
    ws.call(requests.SetStreamServiceSettings(
        streamServiceType='rtmp_custom',
        streamServiceSettings={
            'server': 'rtmp://127.0.0.1:1935/live',
            'key': 'main',
            'use_auth': False,
        }
    ))
    print("Stream service set to rtmp://127.0.0.1:1935/live key=main")
except Exception as e:
    print(f"SetStreamServiceSettings error: {e}")

time.sleep(0.5)

# Start streaming
try:
    result = ws.call(requests.StartStream())
    print(f"Stream started! Result: {result}")

    # Verify
    status = ws.call(requests.GetStreamStatus())
    print(f"Stream active: {status.getOutputActive()}")
    print(f"Stream time: {status.getOutputDuration()} ms")
except Exception as e:
    print(f"Start stream error: {e}")
    # Try forcing start
    try:
        ws.call(requests.StartStream())
    except:
        pass

# Switch to Intro scene
try:
    ws.call(requests.SetCurrentProgramScene(sceneName='Intro'))
    print("Switched to Intro scene")
except Exception as e:
    print(f"Scene switch error: {e}")

# Get scene list
try:
    scenes = ws.call(requests.GetSceneList())
    scene_names = [s['sceneName'] for s in scenes.getScenes()]
    print(f"Available scenes: {scene_names}")
except Exception as e:
    print(f"Scene list error: {e}")

ws.disconnect()
print("Done")
