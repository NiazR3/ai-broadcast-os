"""Tests for persona models, repository, dialogue integration, and API."""
import pytest
from broadcast.agents.persona import (
    PersonaProfile, PersonaRepository, VoiceStyle,
)
from broadcast.agents.models import AgentType, Segment, SegmentType
from broadcast.agents import router


# ── Model tests ────────────────────────────────────────────────────

class TestPersonaModel:
    def test_create_valid_persona(self):
        p = PersonaProfile(
            id="p1", name="Energetic Host",
            agent_type=AgentType.HOST,
            personality_traits=["enthusiastic", "warm"],
            catchphrases=["Let's go!", "That's amazing!"],
            voice_style=VoiceStyle.ENERGETIC,
            default_emotion="excited",
            emotional_range=["excited", "curious", "thoughtful"],
        )
        assert p.id == "p1"
        assert len(p.catchphrases) == 2
        assert p.voice_style == VoiceStyle.ENERGETIC

    def test_persona_default_emotion(self):
        p = PersonaProfile(
            id="p2", name="Calm Host",
            agent_type=AgentType.HOST,
            personality_traits=["calm"],
            catchphrases=[],
            voice_style=VoiceStyle.CALM,
            default_emotion="serene",
            emotional_range=["serene", "professional"],
        )
        assert p.default_emotion == "serene"

    def test_voice_style_enum_values(self):
        assert VoiceStyle.ENERGETIC.value == "energetic"
        assert VoiceStyle.CALM.value == "calm"
        assert VoiceStyle.PROFESSIONAL.value == "professional"
        assert VoiceStyle.CASUAL.value == "casual"
        assert VoiceStyle.WITTY.value == "witty"
        assert VoiceStyle.SERIOUS.value == "serious"


# ── Repository tests ───────────────────────────────────────────────

class TestPersonaRepository:
    @pytest.fixture
    def repo(self):
        return PersonaRepository()

    def test_create_and_get(self, repo):
        p = repo.create(
            name="Host V1", agent_type=AgentType.HOST,
            personality_traits=["fun"], catchphrases=["Yo!"],
            voice_style=VoiceStyle.CASUAL,
            default_emotion="happy",
            emotional_range=["happy", "serious"],
        )
        assert p.id
        assert repo.get(p.id) is p

    def test_get_missing(self, repo):
        assert repo.get("nonexistent") is None

    def test_list_empty(self, repo):
        assert repo.list() == []

    def test_list_after_create(self, repo):
        repo.create(name="A", agent_type=AgentType.HOST,
                    personality_traits=[], catchphrases=[],
                    voice_style=VoiceStyle.CALM, default_emotion="ok",
                    emotional_range=["ok"])
        repo.create(name="B", agent_type=AgentType.COHOST,
                    personality_traits=[], catchphrases=[],
                    voice_style=VoiceStyle.WITTY, default_emotion="silly",
                    emotional_range=["silly"])
        names = [p.name for p in repo.list()]
        assert "A" in names
        assert "B" in names

    def test_update(self, repo):
        p = repo.create(name="Original", agent_type=AgentType.HOST,
                        personality_traits=[], catchphrases=[],
                        voice_style=VoiceStyle.CALM, default_emotion="ok",
                        emotional_range=["ok"])
        updated = repo.update(p.id, name="Updated")
        assert updated.name == "Updated"
        assert repo.get(p.id).name == "Updated"

    def test_update_missing(self, repo):
        with pytest.raises(ValueError, match="not found"):
            repo.update("ghost", name="X")

    def test_delete(self, repo):
        p = repo.create(name="Temp", agent_type=AgentType.HOST,
                        personality_traits=[], catchphrases=[],
                        voice_style=VoiceStyle.CALM, default_emotion="ok",
                        emotional_range=["ok"])
        assert repo.delete(p.id) is True
        assert repo.get(p.id) is None

    def test_delete_missing(self, repo):
        assert repo.delete("ghost") is False

    def test_create_assigns_id(self, repo):
        p = repo.create(name="AutoID", agent_type=AgentType.HOST,
                        personality_traits=[], catchphrases=[],
                        voice_style=VoiceStyle.CALM, default_emotion="ok",
                        emotional_range=["ok"])
        assert len(p.id) == 12  # matches uuid hex[:12] pattern


# ── Persona-aware dialogue tests ─────────────────────────────────

class TestPersonaAwareDialogue:
    @pytest.fixture
    def repo(self):
        return PersonaRepository()

    @pytest.fixture
    def host_persona(self):
        return PersonaProfile(
            id="hp1", name="Energetic Host",
            agent_type=AgentType.HOST,
            personality_traits=["enthusiastic", "warm"],
            catchphrases=["Let's go!", "This is huge!"],
            voice_style=VoiceStyle.ENERGETIC,
            default_emotion="excited",
            emotional_range=["excited", "curious", "thoughtful"],
        )

    @pytest.fixture
    def cohost_persona(self):
        return PersonaProfile(
            id="cp1", name="Witty Co-Host",
            agent_type=AgentType.COHOST,
            personality_traits=["witty", "sarcastic"],
            catchphrases=["No way!", "I'm shook!"],
            voice_style=VoiceStyle.WITTY,
            default_emotion="amused",
            emotional_range=["amused", "surprised", "skeptical"],
        )

    def test_unassigned_host_behaves_as_before(self):
        """No persona assigned = backward compatible."""
        from broadcast.agents.dialogue import HostAgent
        h = HostAgent()
        seg = Segment(id="intro", type=SegmentType.INTRO, title="Welcome")
        block = h.generate_dialogue(seg)
        assert len(block.lines) >= 1
        assert block.lines[0].emotion is None  # no persona = no emotion

    def test_assigned_persona_sets_emotion(self, host_persona, repo):
        from broadcast.agents.dialogue import HostAgent
        h = HostAgent()
        repo.from_model(host_persona)
        h.assign_persona("hp1", repo)
        seg = Segment(id="seg_1", type=SegmentType.CONTENT, title="AI News", dialogue_prompt="Latest AI breakthroughs")
        block = h.generate_dialogue(seg, repo=repo)
        assert block.lines[0].emotion is not None
        assert block.lines[0].emotion in host_persona.emotional_range

    def test_assigned_cohost_sets_emotion(self, cohost_persona, repo):
        from broadcast.agents.dialogue import CoHostAgent
        c = CoHostAgent()
        repo.from_model(cohost_persona)
        c.assign_persona("cp1", repo)
        seg = Segment(id="seg_1", type=SegmentType.CONTENT, title="Space News")
        block = c.generate_dialogue(seg, host_dialogue="Let's talk space!", repo=repo)
        assert block.lines[0].emotion is not None
        assert block.lines[0].emotion in cohost_persona.emotional_range

    def test_persona_catchphrase_appears_occasionally(self, host_persona, repo):
        from broadcast.agents.dialogue import HostAgent
        h = HostAgent()
        repo.from_model(host_persona)
        h.assign_persona("hp1", repo)
        seg = Segment(id="seg_1", type=SegmentType.INTRO, title="Big Announcement")
        # Run multiple times to check catchphrases appear (cycle is 5 calls)
        catchphrases_found = False
        for _ in range(20):
            block = h.generate_dialogue(seg, repo=repo)
            text = " ".join(l.text for l in block.lines)
            for cp in host_persona.catchphrases:
                if cp.lower() in text.lower():
                    catchphrases_found = True
                    break
            if catchphrases_found:
                break
        assert catchphrases_found, "Catchphrase should appear within 20 generations"

    def test_persona_persists_across_calls(self, host_persona, repo):
        from broadcast.agents.dialogue import HostAgent
        h = HostAgent()
        repo.from_model(host_persona)
        h.assign_persona("hp1", repo)
        retrieved = h.get_persona(repo)
        assert retrieved is not None
        assert retrieved.id == "hp1"
        assert retrieved.name == "Energetic Host"

    def test_remove_persona_reverts_behavior(self, host_persona, repo):
        from broadcast.agents.dialogue import HostAgent
        h = HostAgent()
        repo.from_model(host_persona)
        h.assign_persona("hp1", repo)
        h.remove_persona()
        seg = Segment(id="seg_1", type=SegmentType.CONTENT, title="Test")
        block = h.generate_dialogue(seg, repo=None)
        assert block.lines[0].emotion is None  # back to default
        assert h.get_persona(repo) is None

    def test_different_segment_types_get_different_emotions(self, host_persona, repo):
        from broadcast.agents.dialogue import HostAgent
        h = HostAgent()
        repo.from_model(host_persona)
        h.assign_persona("hp1", repo)

        seg_intro = Segment(id="intro", type=SegmentType.INTRO, title="Welcome")
        seg_content = Segment(id="main", type=SegmentType.CONTENT, title="Topic")
        seg_outro = Segment(id="outro", type=SegmentType.OUTRO, title="Bye")

        intro_emotion = h.generate_dialogue(seg_intro, repo=repo).lines[0].emotion
        content_emotion = h.generate_dialogue(seg_content, repo=repo).lines[0].emotion
        outro_emotion = h.generate_dialogue(seg_outro, repo=repo).lines[0].emotion

        # All should be within the emotional range
        assert intro_emotion in host_persona.emotional_range
        assert content_emotion in host_persona.emotional_range
        assert outro_emotion in host_persona.emotional_range

        # Intro and outro should differ (first vs last in range) if range has 3+ emotions
        if len(host_persona.emotional_range) >= 3:
            assert intro_emotion != outro_emotion


# ── API tests ──────────────────────────────────────────────────────

class TestPersonaAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from broadcast.main import app
        return TestClient(app)

    def test_list_personas_empty(self, client):
        resp = client.get("/agent/personas")
        assert resp.status_code == 200
        assert resp.json() == []

    def _create_persona(self, client) -> str:
        """Helper: create a persona and return its ID."""
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
        return resp.json()["id"]

    def test_create_persona(self, client):
        pid = self._create_persona(client)
        assert pid is not None

    def test_create_persona_validates_required(self, client):
        resp = client.post("/agent/personas", json={})
        assert resp.status_code == 422

    def test_get_persona(self, client):
        pid = self._create_persona(client)
        resp = client.get(f"/agent/personas/{pid}")
        assert resp.status_code == 200
        assert resp.json()["id"] == pid

    def test_get_nonexistent_persona(self, client):
        resp = client.get("/agent/personas/nonexistent")
        assert resp.status_code == 404

    def test_update_persona(self, client):
        pid = self._create_persona(client)
        resp = client.put(f"/agent/personas/{pid}", json={"name": "Updated Host"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Host"

    def test_update_nonexistent(self, client):
        resp = client.put("/agent/personas/nope", json={"name": "X"})
        assert resp.status_code == 404

    def test_delete_persona(self, client):
        pid = self._create_persona(client)
        resp = client.delete(f"/agent/personas/{pid}")
        assert resp.status_code == 200
        resp = client.get(f"/agent/personas/{pid}")
        assert resp.status_code == 404

    def test_delete_nonexistent(self, client):
        resp = client.delete("/agent/personas/nope")
        assert resp.status_code == 404

    def test_assign_host_persona(self, client):
        pid = self._create_persona(client)
        resp = client.post(f"/agent/host/persona/{pid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["assigned"] is True
        assert data["persona_id"] == pid
        assert data["agent"] == "host"

    def test_assign_cohost_persona(self, client):
        pid = self._create_persona(client)
        resp = client.post(f"/agent/cohost/persona/{pid}")
        assert resp.status_code == 200
        assert resp.json()["assigned"] is True

    def test_assign_nonexistent_persona(self, client):
        resp = client.post("/agent/host/persona/bogus")
        assert resp.status_code == 404

    def test_remove_host_persona(self, client):
        pid = self._create_persona(client)
        client.post(f"/agent/host/persona/{pid}")
        resp = client.delete("/agent/host/persona")
        assert resp.status_code == 200
        assert resp.json()["removed"] is True

    def test_remove_cohost_persona(self, client):
        pid = self._create_persona(client)
        client.post(f"/agent/cohost/persona/{pid}")
        resp = client.delete("/agent/cohost/persona")
        assert resp.status_code == 200

    def test_delete_rejects_if_assigned_to_host(self, client):
        pid = self._create_persona(client)
        client.post(f"/agent/host/persona/{pid}")
        resp = client.delete(f"/agent/personas/{pid}")
        assert resp.status_code == 409  # Conflict — persona in use

    def test_delete_rejects_if_assigned_to_cohost(self, client):
        pid = self._create_persona(client)
        client.post(f"/agent/cohost/persona/{pid}")
        resp = client.delete(f"/agent/personas/{pid}")
        assert resp.status_code == 409

    def test_persona_affects_dialogue_through_api(self, client):
        # Create persona
        pid = client.post("/agent/personas", json={
            "name": "Excited Host", "agent_type": "host",
            "personality_traits": ["excited"], "catchphrases": ["Wow!"],
            "voice_style": "energetic", "default_emotion": "excited",
            "emotional_range": ["excited", "amazed"],
        }).json()["id"]

        # Assign to host
        client.post(f"/agent/host/persona/{pid}")

        # Create episode + segment + generate dialogue
        ep = client.post("/agent/episode", json={"title": "Morning Show"}).json()
        client.post(f"/agent/episode/{ep['id']}/segment",
                    json={"id": "intro", "type": "intro", "title": "Welcome!"})
        client.post(f"/agent/episode/{ep['id']}/load")
        client.post("/agent/director/next")
        resp = client.post("/agent/director/generate")
        data = resp.json()
        # Host dialogue should have emotion set
        assert data["host"]["lines"][0]["emotion"] is not None
        assert data["host"]["lines"][0]["emotion"] in ["excited", "amazed"]


def get_health_status(persona: PersonaProfile) -> dict:
    """JavaScript getHealthStatus logic ported to Python for testing."""
    # Check if persona is assigned to host or co-host (not applicable here, just simulate)
    # For UI test we ignore assignment; just compute completeness.
    has_name = bool(persona.name and persona.name.strip())
    has_traits = len(persona.personality_traits) > 0
    has_catchphrases = len(persona.catchphrases) > 0
    has_emotions = len(persona.emotional_range) > 0
    has_background = bool(persona.background_story and persona.background_story.strip())

    completeness = (
        (1 if has_name else 0) +
        (1 if has_traits else 0) +
        (1 if has_catchphrases else 0) +
        (1 if has_emotions else 0) +
        (1 if has_background else 0)
    ) / 5

    if completeness >= 0.8:
        return {\"text\": \"Healthy\", \"color\": \"text-green-600\"}
    elif completeness >= 0.5:
        return {\"text\": \"Needs Work\", \"color\": \"text-yellow-600\"}
    else:
        return {\"text\": \"Incomplete\", \"color\": \"text-red-600\"}


class TestPersonaUI:
    def test_persona_health_indicator(self):
        # Healthy persona
        healthy = PersonaProfile(
            id=\"h1\",
            name=\"Healthy Host\",
            agent_type=AgentType.HOST,
            personality_traits=[\"enthusiastic\", \"warm\"],
            catchphrases=[\"Let's go!\"],
            voice_style=VoiceStyle.ENERGETIC,
            default_emotion=\"excited\",
            emotional_range=[\"excited\", \"curious\", \"thoughtful\"],
            background_story=\"Experienced host\",
        )
        status = get_health_status(healthy)
        assert status[\"text\"] == \"Healthy\"
        assert status[\"color\"] == \"text-green-600\"

        # Needs work (missing some fields)
        medium = PersonaProfile(
            id=\"m1\",
            name=\"Medium Host\",
            agent_type=AgentType.HOST,
            personality_traits=[],  # missing traits
            catchphrases=[\"Okay\"],
            voice_style=VoiceStyle.CALM,
            default_emotion=\"ok\",
            emotional_range=[\"ok\", \"fine\"],
            background_story=\"\",  # missing background
        )
        status = get_health_status(medium)
        assert status[\"text\"] == \"Needs Work\"
        assert status[\"color\"] == \"text-yellow-600\"

        # Incomplete (missing many fields)
        low = PersonaProfile(
            id=\"l1\",
            name=\"\",  # empty name
            agent_type=AgentType.HOST,
            personality_traits=[],
            catchphrases=[],
            voice_style=VoiceStyle.CASUAL,
            default_emotion=\"neutral\",
            emotional_range=[],
            background_story=\"\",
        )
        status = get_health_status(low)
        assert status[\"text\"] == \"Incomplete\"
        assert status[\"color\"] == \"text-red-600\"


