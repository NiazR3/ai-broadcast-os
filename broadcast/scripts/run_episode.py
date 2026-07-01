"""Orchestrate AI Revolution 2026 episode: create, load, run with auto OBS scene switching."""
import sys, time, requests
sys.stdout.reconfigure(encoding='utf-8')

API = "http://localhost:8100/api"
from obsws_python import ReqClient
obs = ReqClient(host='127.0.0.1', port=4455, password='cAaPLQ7HAkc3mMOv', timeout=5)

SEGMENTS = [
    ("intro",    "intro",  "Welcome & Intro",              45, "Intro",          "Welcome to AI Revolution 2026"),
    ("llm",      "content","LLM Landscape 2026",           120,"LLM Landscape",  "State of large language models in 2026"),
    ("agents",   "content","AI Agents & Automation",       120,"AI Agents",      "How AI agents transform workflows"),
    ("guest",    "guest",  "Guest Interview: The Future",  180,"Guest Interview","Ethical implications of AI"),
    ("sponsor",  "ad",     "Sponsor Break",                30, "Sponsor Break",  "Sponsor message"),
    ("outro",    "outro",  "Wrap-Up & Outro",               45,"Outro",          "Thanks and call to action"),
]

# 1. Create episode
print("=== AI Revolution 2026 - Episode Broadcast ===")
r = requests.post(f"{API}/agent/episode", json={"title": "AI Revolution 2026"})
ep = r.json()
eid = ep["id"]
print(f"Episode created: {eid}")

# 2. Add segments
for sid, stype, title, dur, scene, prompt in SEGMENTS:
    r = requests.post(f"{API}/agent/episode/{eid}/segment", json={
        "id": sid, "type": stype, "title": title,
        "duration_seconds": dur, "scene_name": scene,
        "dialogue_prompt": prompt,
    })
    s = r.json()["segments"][-1]
    print(f"  Segment {s['order']}: {s['title']} -> {s['scene_name']}")

# 3. Load into director
r = requests.post(f"{API}/agent/episode/{eid}/load")
print(f"Loaded: {r.json()['title']} ({r.json()['segment_count']} segments)")

# 4. Run through segments
for i in range(6):
    print(f"\n--- SEGMENT {i+1}/6 ---")
    r = requests.post(f"{API}/agent/director/next")
    seg = r.json()["segment"]
    print(f"  {seg['title']} / Scene: {seg['scene_name']}")

    # Switch OBS scene
    obs.set_current_program_scene(seg["scene_name"])
    print(f"  OBS switched to '{seg['scene_name']}'")

    # Generate dialogue
    r = requests.post(f"{API}/agent/director/generate")
    if r.status_code == 200:
        g = r.json()
        ht = g.get("host",{}).get("lines",[{}])[0].get("text","")[:100]
        ct = g.get("cohost",{}).get("lines",[{}])[0].get("text","")[:100]
        print(f"  Host: {ht}...")
        print(f"  Co-host: {ct}...")

    # Wait (accelerated)
    wait = min(seg["duration_seconds"], 8)
    for remaining in range(wait, 0, -1):
        sys.stdout.write(f"\r  > Playing... {remaining}s  ")
        sys.stdout.flush()
        time.sleep(1)
    sys.stdout.write(f"\n  > Segment complete!\n")

# 5. Final status
scenes = [s["sceneName"] for s in obs.get_scene_list().scenes]
current = obs.get_current_program_scene().current_program_scene_name
s = obs.get_stream_status()
print(f"\n=== EPISODE COMPLETE ===")
print(f"  Final scene: {current}")
print(f"  Stream active: {s.output_active} ({s.output_duration}ms)")
obs.disconnect()

# Verify stream is still live
r = requests.get(f"{API}/broadcast/status")
if r.status_code == 200:
    mux = r.json()
    print(f"  Mux active: {mux.get('active', 'unknown')}")
