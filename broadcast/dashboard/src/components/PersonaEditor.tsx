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
    if (!name.trim()) {
      setError("Name is required");
      return;
    }

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
        <div className="flex justify-between items-start mb-4">
          <h3 className="font-semibold text-lg">{persona ? "Edit Persona" : "New Persona"}</h3>
          <button onClick={onCancel} className="text-gray-400 hover:text-gray-600">
            ✕
          </button>
        </div>

        <form onSubmit={e => { e.preventDefault(); handleSave(); }} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Name *</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Morning Show Host"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Agent Type</label>
              <select
                value={agentType}
                onChange={e => setAgentType(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {AGENT_TYPES.map(t => (
                  <option key={t} value={t}>
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Voice Style</label>
              <select
                value={voiceStyle}
                onChange={e => setVoiceStyle(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {VOICE_STYLES.map(v => (
                  <option key={v} value={v}>
                    {v.charAt(0).toUpperCase() + v.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Personality Traits</label>
            <p className="text-xs text-gray-500 mb-1">Comma-separated (e.g., enthusiastic, warm, curious)</p>
            <input
              type="text"
              value={traits}
              onChange={e => setTraits(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="enthusiastic, warm, curious"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Catchphrases</label>
            <p className="text-xs text-gray-500 mb-1">Comma-separated (e.g., Let's go!, That's fire!)</p>
            <input
              type="text"
              value={catchphrases}
              onChange={e => setCatchphrases(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Let's go!, That's fire!"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Default Emotion</label>
              <input
                type="text"
                value={defaultEmotion}
                onChange={e => setDefaultEmotion(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="excited"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Emotional Range</label>
              <p className="text-xs text-gray-500 mb-1">Comma-separated (e.g., excited, curious, thoughtful)</p>
              <input
                type="text"
                value={emotions}
                onChange={e => setEmotions(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="excited, curious, thoughtful"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Background Story</label>
            <p className="text-xs text-gray-500 mb-1">Short bio for the persona...</p>
            <textarea
              value={background}
              onChange={e => setBackground(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 h-32 resize-none"
              placeholder="Short bio for the persona..."
            />
          </div>

          {error && (
            <div className="mt-2 p-3 bg-red-50 border-l-4 border-red-200 text-red-800 text-sm">
              {error}
            </div>
          )}

          <div className="flex justify-end pt-4 space-x-3">
            <button
              type="button"
              onClick={onCancel}
              className="px-5 py-3 text-sm font-medium border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-5 py-3 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Persona"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
