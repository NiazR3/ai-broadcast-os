import { useState, useEffect, useRef, useCallback } from "react";
import type { PersonaProfile } from "../lib/api";
import { createPersona, updatePersona } from "../lib/api";

const VOICE_STYLES = ["energetic", "calm", "professional", "casual", "witty", "serious"] as const;
const AGENT_TYPES = ["host", "cohost", "director", "producer"] as const;

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

  const dialogRef = useRef<HTMLDivElement>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);

  // Focus trap and Escape handler
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === "Escape") {
      onCancel();
      return;
    }

    // Focus trap: keep focus within the dialog
    if (e.key === "Tab" && dialogRef.current) {
      const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );
      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    }
  }, [onCancel]);

  useEffect(() => {
    // Focus the name input on mount
    nameInputRef.current?.focus();

    // Add keyboard listeners
    document.addEventListener("keydown", handleKeyDown);

    // Prevent body scroll while modal is open
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [handleKeyDown]);

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

  const headingId = "persona-editor-heading";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-bg-base/80 animate-fade-in"
      onClick={onCancel}
      role="presentation"
    >
      <div
        ref={dialogRef}
        className="card card--elevated w-full max-w-lg max-h-[90vh] overflow-y-auto animate-fade-in-down"
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
      >
        {/* ── Header ── */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h3 id={headingId} className="text-base font-semibold text-text">
              {persona ? "Edit Persona" : "New Persona"}
            </h3>
            <p className="mt-0.5 text-xs text-text-secondary">
              {persona ? "Update the personality profile" : "Create a new AI personality"}
            </p>
          </div>
          <button
            onClick={onCancel}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-text-muted transition-colors hover:bg-bg-hover hover:text-text"
            aria-label="Close dialog"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* ── Form ── */}
        <form onSubmit={e => { e.preventDefault(); handleSave(); }} className="space-y-5">
          {/* Name */}
          <div>
            <label htmlFor="persona-name" className="mb-1.5 block text-sm font-medium text-text-secondary">
              Name <span className="text-danger">*</span>
            </label>
            <input
              ref={nameInputRef}
              id="persona-name"
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              className="input-field"
              placeholder="Morning Show Host"
              required
            />
          </div>

          {/* Agent Type + Voice Style — side by side */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="persona-agent-type" className="mb-1.5 block text-sm font-medium text-text-secondary">Agent Type</label>
              <select
                id="persona-agent-type"
                value={agentType}
                onChange={e => setAgentType(e.target.value as typeof AGENT_TYPES[number])}
                className="input-field"
              >
                {AGENT_TYPES.map(t => (
                  <option key={t} value={t}>
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="persona-voice-style" className="mb-1.5 block text-sm font-medium text-text-secondary">Voice Style</label>
              <select
                id="persona-voice-style"
                value={voiceStyle}
                onChange={e => setVoiceStyle(e.target.value as typeof VOICE_STYLES[number])}
                className="input-field"
              >
                {VOICE_STYLES.map(v => (
                  <option key={v} value={v}>
                    {v.charAt(0).toUpperCase() + v.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Personality Traits */}
          <div>
            <label htmlFor="persona-traits" className="mb-1.5 block text-sm font-medium text-text-secondary">Personality Traits</label>
            <p className="mb-1 text-xs text-text-muted">Comma-separated (e.g., enthusiastic, warm, curious)</p>
            <input
              id="persona-traits"
              type="text"
              value={traits}
              onChange={e => setTraits(e.target.value)}
              className="input-field"
              placeholder="enthusiastic, warm, curious"
            />
          </div>

          {/* Catchphrases */}
          <div>
            <label htmlFor="persona-catchphrases" className="mb-1.5 block text-sm font-medium text-text-secondary">Catchphrases</label>
            <p className="mb-1 text-xs text-text-muted">Comma-separated (e.g., Let's go!, That's fire!)</p>
            <input
              id="persona-catchphrases"
              type="text"
              value={catchphrases}
              onChange={e => setCatchphrases(e.target.value)}
              className="input-field"
              placeholder="Let's go!, That's fire!"
            />
          </div>

          {/* Default Emotion + Emotional Range — side by side */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="persona-default-emotion" className="mb-1.5 block text-sm font-medium text-text-secondary">Default Emotion</label>
              <input
                id="persona-default-emotion"
                type="text"
                value={defaultEmotion}
                onChange={e => setDefaultEmotion(e.target.value)}
                className="input-field"
                placeholder="excited"
              />
            </div>
            <div>
              <label htmlFor="persona-emotions" className="mb-1.5 block text-sm font-medium text-text-secondary">Emotional Range</label>
              <p className="mb-1 text-xs text-text-muted">Comma-separated</p>
              <input
                id="persona-emotions"
                type="text"
                value={emotions}
                onChange={e => setEmotions(e.target.value)}
                className="input-field"
                placeholder="excited, curious, thoughtful"
              />
            </div>
          </div>

          {/* Background Story */}
          <div>
            <label htmlFor="persona-background" className="mb-1.5 block text-sm font-medium text-text-secondary">Background Story</label>
            <p className="mb-1 text-xs text-text-muted">Short bio for the persona...</p>
            <textarea
              id="persona-background"
              value={background}
              onChange={e => setBackground(e.target.value)}
              className="input-field min-h-[100px] resize-y"
              placeholder="Short bio for the persona..."
            />
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2.5 rounded-lg border border-danger/30 bg-danger-bg px-4 py-3 text-sm text-danger" role="alert">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0" aria-hidden="true">
                <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              {error}
            </div>
          )}

          {/* Footer actions */}
          <div className="flex justify-end gap-3 border-t border-border pt-5">
            <button type="button" onClick={onCancel} className="btn btn-ghost">
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="btn btn-primary"
            >
              {saving ? (
                <span className="flex items-center gap-2">
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="31.4 31.4" strokeLinecap="round" />
                  </svg>
                  Saving...
                </span>
              ) : (
                "Save Persona"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
