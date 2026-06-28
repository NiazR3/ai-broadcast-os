import { useState } from "react";
import type { PersonaProfile } from "../lib/api";
import { createPersona, updatePersona } from "../lib/api";

const VOICE_STYLES = ["energetic", "calm", "professional", "casual", "witty", "serious"];
const AGENT_TYPES = ["host", "cohost", "director", "producer"];

interface PersonaEditorProps {
  persona: PersonaProfile | null; // null = creating new
  onSave: () => void;
  onCancel: () => void;
}

export function PersonaEditor({ persona, onSave, onCancel }: PersonaEditorProps) {
  const [name, setName] = useState(persona?.name ?? "");
  const [agentType, setAgentType] = useState(persona?.agent_type ?? "host");
  const [voiceStyle, setVoiceStyle] = useState(persona?.voice_style ?? "casual");
  const [traits, setTraits] = useState(persona?.personality_traits.join(", ") ?? "");
  const [catchphrases, setCatchphrases] = useState(persona?.catchphrases.join(", ") ?? "");
  const [emotions, setEmotions] = useState(persona?.emotional_range.join(", ") ?? "");
  const [defaultEmotion, setDefaultEmotion] = useState(persona?.default_emotion ?? "neutral");
  const [background, setBackground] = useState(persona?.background_story ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    if (!name.trim()) { setError("Name is required"); return; }
    setSaving(true);
    setError(null);
    const payload = {
      name: name.trim(),
      agent_type: agentType,
      voice_style: voiceStyle,
      personality_traits: traits.split(",").map(s => s.trim()).filter(Boolean),
      catchphrases: catchphrases.split(",").map(s => s.trim()).filter(Boolean),
      emotional_range: emotions.split(",").map(s => s.trim()).filter(Boolean),
      default_emotion: defaultEmotion.trim(),
      background_story: background.trim(),
    };
    try {
      if (persona) {
        await updatePersona(persona.id, payload);
      } else {
        await createPersona(payload);
      }
      onSave();
    } catch {
      setError("Failed to save persona");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onCancel}>
      <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <h3 className="font-semibold text-lg mb-4">{persona ? "Edit Persona" : "New Persona"}</h3>

        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Name</label>
            <input type="text" value={name} onChange={e => setName(e.target.value)}
              className="w-full px-3 py-2 border rounded text-sm" placeholder="Morning Show Host" />
          </div>

          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-600 mb-1">Agent Type</label>
              <select value={agentType} onChange={e => setAgentType(e.target.value)}
                className="w-full px-3 py-2 border rounded text-sm">
                {AGENT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-600 mb-1">Voice Style</label>
              <select value={voiceStyle} onChange={e => setVoiceStyle(e.target.value)}
                className="w-full px-3 py-2 border rounded text-sm">
                {VOICE_STYLES.map(v => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Personality Traits (comma-separated)</label>
            <input type="text" value={traits} onChange={e => setTraits(e.target.value)}
              className="w-full px-3 py-2 border rounded text-sm" placeholder="enthusiastic, warm, curious" />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Catchphrases (comma-separated)</label>
            <input type="text" value={catchphrases} onChange={e => setCatchphrases(e.target.value)}
              className="w-full px-3 py-2 border rounded text-sm" placeholder="Let's go!, That's fire!" />
          </div>

          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-600 mb-1">Default Emotion</label>
              <input type="text" value={defaultEmotion} onChange={e => setDefaultEmotion(e.target.value)}
                className="w-full px-3 py-2 border rounded text-sm" />
            </div>
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-600 mb-1">Emotional Range (comma-separated)</label>
              <input type="text" value={emotions} onChange={e => setEmotions(e.target.value)}
                className="w-full px-3 py-2 border rounded text-sm" placeholder="excited, curious, thoughtful" />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Background Story</label>
            <textarea value={background} onChange={e => setBackground(e.target.value)}
              className="w-full px-3 py-2 border rounded text-sm h-20 resize-none"
              placeholder="Short bio for the persona..." />
          </div>
        </div>

        {error && <p className="text-sm text-red-600 mt-2">{error}</p>}

        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onCancel} className="px-4 py-2 text-sm border rounded hover:bg-gray-50">Cancel</button>
          <button onClick={handleSave} disabled={saving}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50">
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
