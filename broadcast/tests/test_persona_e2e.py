"""End-to-end test for persona workflow."""
from fastapi.testclient import TestClient
from broadcast.main import app

def test_full_persona_workflow():
    client = TestClient(app)

    # 1. Create persona
    resp = client.post("/agent/personas", json={
        "name": "Energetic Host",
        "agent_type": "host",
        "personality_traits": ["enthusiastic", "warm"],
        "catchphrases": ["Let's go!"],
        "voice_style": "energetic",
        "default_emotion": "excited",
        "emotional_range": ["excited", "curious"],
        "background_story": "A high-energy morning show host",
    })
    assert resp.status_code == 200
    pid = resp.json()["id"]
    assert pid is not None

    # 2. Assign to host
    resp = client.post(f"/agent/host/persona/{pid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["assigned"] is True
    assert data["persona_id"] == pid
    assert data["agent"] == "host"

    # 3. Create episode + segment + generate dialogue
    ep = client.post("/agent/episode", json={"title": "Morning Show"}).json()
    client.post(f"/agent/episode/{ep['id']}/segment",
                json={"id": "intro", "type": "intro", "title": "Welcome!"})
    client.post(f"/agent/episode/{ep['id']}/load")
    client.post("/agent/director/next")
    resp = client.post("/agent/director/generate")
    assert resp.status_code == 200
    data = resp.json()
    # Host dialogue should have emotion set
    assert data["host"]["lines"][0]["emotion"] is not None
    assert data["host"]["lines"][0]["emotion"] in ["excited", "curious"]

    # 4. Unassign persona from host
    resp = client.delete("/agent/host/persona")
    assert resp.status_code == 200
    assert resp.json()["removed"] is True

    # 5. Delete persona and verify cleanup
    resp = client.delete(f"/agent/personas/{pid}")
    assert resp.status_code == 200
    resp = client.get(f"/agent/personas/{pid}")
    assert resp.status_code == 404

if __name__ == "__main__":
    test_full_persona_workflow()
    print("All tests passed!")
