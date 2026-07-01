import { useState } from "react";
import { API_BASE } from "../lib/api";

interface PlatformKeys {
  twitch: string;
  youtube: string;
  facebook: string;
}

const PLATFORM_CONFIGS = [
  { key: "twitch" as const, label: "Twitch" },
  { key: "youtube" as const, label: "YouTube" },
  { key: "facebook" as const, label: "Facebook" },
];

export function ConfigPanel() {
  const [keys, setKeys] = useState<PlatformKeys>({
    twitch: "",
    youtube: "",
    facebook: "",
  });
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({
    twitch: false,
    youtube: false,
    facebook: false,
  });
  const [configured, setConfigured] = useState<Record<string, boolean>>({
    twitch: false,
    youtube: false,
    facebook: false,
  });
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Record<string, boolean>>({
    twitch: false,
    youtube: false,
    facebook: false,
  });

  const handleSave = async () => {
    setError(null);
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/broadcast/platforms`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(keys),
      });
      if (res.ok) {
        // Mark configured for platforms that had keys entered
        const newConfigured = { ...configured };
        (Object.keys(keys) as Array<keyof PlatformKeys>).forEach((k) => {
          if (keys[k].trim()) {
            newConfigured[k] = true;
          }
        });
        setConfigured(newConfigured);
        // Clear the input fields
        setKeys({ twitch: "", youtube: "", facebook: "" });
        setEditing({ twitch: false, youtube: false, facebook: false });
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
      } else {
        const data = await res.json().catch(() => null);
        setError(data?.detail || `Request failed (${res.status})`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save configuration");
    }
    setSaving(false);
  };

  const toggleShow = (platform: string) => {
    setShowKeys((prev) => ({ ...prev, [platform]: !prev[platform] }));
  };

  const startEditing = (platform: string) => {
    setEditing((prev) => ({ ...prev, [platform]: true }));
  };

  const hasAnyKey = Object.values(keys).some((k) => k.trim().length > 0);
  const allConfigured = Object.values(configured).every((c) => c);
  const someConfigured = Object.values(configured).some((c) => c);

  return (
    <div className="card space-y-5">
      <div className="section-header">
        <h3 className="section-header__title">Platform Configuration</h3>
        <div className="flex items-center gap-2">
          {someConfigured && (
            <span className="text-xs text-text-muted">
              <span className="data-value">{Object.values(configured).filter(Boolean).length}</span> of{" "}
              <span className="data-value">{PLATFORM_CONFIGS.length}</span> configured
            </span>
          )}
          {allConfigured && (
            <span className="inline-flex items-center gap-1 text-xs text-live font-medium">
              <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                <path d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z" />
              </svg>
              All Set
            </span>
          )}
          {saved && (
            <span className="inline-flex items-center gap-1.5 text-live text-sm font-medium animate-fade-in" role="status">
              <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                <path d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z" />
              </svg>
              Keys Saved
            </span>
          )}
        </div>
      </div>

      {PLATFORM_CONFIGS.map(({ key: platform, label }) => (
        <div key={platform} className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="block text-xs font-medium text-text-secondary uppercase tracking-wider" htmlFor={`stream-key-${platform}`}>
              {label}
            </label>
            {/* Configured indicator */}
            {configured[platform] && !editing[platform] && (
              <span className="inline-flex items-center gap-1 text-xs text-live font-medium">
                <svg className="w-3 h-3" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                  <path d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z" />
                </svg>
                Configured
              </span>
            )}
          </div>
          <div className="relative">
            {editing[platform] || !configured[platform] ? (
              <>
                <input
                  id={`stream-key-${platform}`}
                  type={showKeys[platform] ? "text" : "password"}
                  value={keys[platform]}
                  onChange={(e) =>
                    setKeys((prev) => ({ ...prev, [platform]: e.target.value }))
                  }
                  className="input-field pr-20"
                  placeholder="Enter stream key..."
                  autoComplete="off"
                />
                <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => toggleShow(platform)}
                    className="p-1.5 text-text-muted hover:text-text-secondary transition-colors rounded focus-visible:outline-2 focus-visible:outline-brand"
                    aria-label={showKeys[platform] ? "Hide stream key" : "Show stream key"}
                  >
                    {showKeys[platform] ? (
                      <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M.5 8s1.5-5 7.5-5 7.5 5 7.5 5-1.5 5-7.5 5S.5 8 .5 8zm2.26-.57A10.53 10.53 0 008 10.5a10.5 10.5 0 005.24-3.07A10.52 10.52 0 008 4.5a10.52 10.52 0 00-5.24 2.93z" />
                        <path d="M8 6a2 2 0 100 4 2 2 0 000-4z" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M13.36 2.64a.75.75 0 010 1.06L4.7 12.36a.75.75 0 11-1.06-1.06L12.3 2.64a.75.75 0 011.06 0z" />
                        <path d="M2.9 4.2A10.56 10.56 0 00.5 8s1.5 5 7.5 5c1.22 0 2.33-.2 3.3-.52l-1.12-1.12A5.98 5.98 0 018 11.5a5.99 5.99 0 01-5.24-3.07 10.55 10.55 0 012.28-2.44L2.9 4.2zm4-1.5c.17-.01.35-.02.53-.02 6 0 7.5 5 7.5 5a11 11 0 01-1.24 2.3l-1.1-1.1A5.99 5.99 0 008 4.5c-.46 0-.9.05-1.32.14L6.9 2.7z" />
                      </svg>
                    )}
                  </button>
                  {/* Cancel editing button when configured and editing */}
                  {configured[platform] && (
                    <button
                      type="button"
                      onClick={() => {
                        setEditing((prev) => ({ ...prev, [platform]: false }));
                        setKeys((prev) => ({ ...prev, [platform]: "" }));
                      }}
                      className="p-1.5 text-text-muted hover:text-text-secondary transition-colors rounded"
                      aria-label="Cancel editing"
                    >
                      <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                        <line x1="18" y1="6" x2="6" y2="18" />
                        <line x1="6" y1="6" x2="18" y2="18" />
                      </svg>
                    </button>
                  )}
                </div>
              </>
            ) : (
              // Configured state — show summary
              <div
                className="flex items-center justify-between input-field cursor-pointer"
                onClick={() => startEditing(platform)}
                onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); startEditing(platform); } }}
                tabIndex={0}
                role="button"
                aria-label={`Edit ${label} stream key`}
              >
                <span className="text-text-muted text-sm font-mono">
                  &bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;
                </span>
                <span className="text-xs text-text-muted">Click to update</span>
              </div>
            )}
          </div>
        </div>
      ))}

      {error && (
        <div className="bg-danger-bg border border-danger/30 rounded-lg px-4 py-3 flex items-start gap-2 animate-fade-in" role="alert">
          <span className="text-danger text-xs leading-none mt-0.5 font-bold" aria-hidden="true">!</span>
          <p className="text-danger text-xs font-medium flex-1">{error}</p>
          <button
            onClick={() => setError(null)}
            className="text-xs text-text-muted hover:text-text-secondary"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="flex items-center gap-3 pt-1">
        <button
          onClick={handleSave}
          disabled={!hasAnyKey || saving}
          className="btn btn-primary"
        >
          {saving ? (
            <>
              <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Saving...
            </>
          ) : (
            "Save Keys"
          )}
        </button>
        {!hasAnyKey && !saved && !someConfigured && (
          <span className="text-text-muted text-xs">Enter at least one stream key to save</span>
        )}
        {!hasAnyKey && allConfigured && (
          <span className="text-text-muted text-xs">All platforms configured. Click a key field to update it.</span>
        )}
      </div>
    </div>
  );
}
