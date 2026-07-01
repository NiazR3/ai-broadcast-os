"""Configure OBS stream settings and start streaming to local relay."""
import asyncio
import json
import sys
sys.path.insert(0, r'C:\Users\MezbiN\broadcast')

from broadcast.obs.controller import ObsController
from broadcast.config import Settings

async def main():
    settings = Settings()
    obs = ObsController(
        host=settings.obs_host or '127.0.0.1',
        port=settings.obs_port or 4455,
        password=settings.obs_password or '',
    )

    # Connect to OBS
    print("Connecting to OBS...")
    await obs.connect()
    print("Connected!")

    # First, check if streaming
    try:
        stream_status = await obs._client.call(obs._client.request_builder.GetStreamStatus())
        print(f"Streaming: {stream_status.outputActive}")
        # Try to stop if active
        if stream_status.outputActive:
            print("Stopping current stream...")
            await obs._client.call(obs._client.request_builder.StopStream())
            await asyncio.sleep(1)
    except Exception as e:
        print(f"Error getting stream status: {e}")

    # Set stream service to local relay
    try:
        await obs._client.call(
            obs._client.request_builder.SetStreamServiceSettings(
                streamServiceType='rtmp_custom',
                streamServiceSettings={
                    'server': 'rtmp://127.0.0.1:1935/live',
                    'key': 'main',
                    'use_auth': False,
                }
            )
        )
        print("Stream service set to rtmp://127.0.0.1:1935/live key=main")
    except Exception as e:
        print(f"Error setting stream service: {e}")

    await asyncio.sleep(0.5)

    # Start streaming
    print("Starting stream...")
    try:
        result = await obs._client.call(obs._client.request_builder.StartStream())
        print(f"Stream started! Result: {result}")

        # Verify
        stream_status = await obs._client.call(obs._client.request_builder.GetStreamStatus())
        print(f"Stream active: {stream_status.outputActive}")
        print(f"Stream time: {stream_status.outputDuration} ms")
    except Exception as e:
        print(f"Error starting stream: {e}")

    # Get scene list to verify connection
    scenes = await obs.get_scene_list()
    print(f"Available scenes: {scenes}")

    # Switch to Intro scene
    print("Switching to Intro scene...")
    try:
        await obs.switch_scene('Intro')
        print("Switched to Intro")
    except Exception as e:
        print(f"Error switching scene: {e}")

    await obs.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
