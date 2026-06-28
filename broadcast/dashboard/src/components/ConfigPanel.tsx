import { useState } from "react";
import { API_BASE } from "../lib/api";

interface PlatformKeys {
  twitch: string;
  youtube: string;
  facebook: string;
}

export function ConfigPanel() {
  const [keys, setKeys] = useState<PlatformKeys>({
    twitch: "",
    youtube: "",
    facebook: "",
  });
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/broadcast/platforms`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(keys),
      });
      if (res.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      } else {
        const data = await res.json().catch(() => null);
        setError(data?.detail || `Request failed (${res.status})`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save configuration");
    }
  };

  return (
    <div className="space-y-4">
      <h3 className="font-semibold">Platform Configuration</h3>
      {(["twitch", "youtube", "facebook"] as const).map((platform) => (
        <div key={platform}>
          <label className="block text-sm font-medium text-gray-700 capitalize mb-1">
            {platform} Stream Key
          </label>
          <input
            type="password"
            value={keys[platform]}
            onChange={(e) =>
              setKeys((prev) => ({ ...prev, [platform]: e.target.value }))
            }
            className="w-full px-3 py-2 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Enter stream key..."
          />
        </div>
      ))}
      {error && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
          {error}
        </div>
      )}
      <button
        onClick={handleSave}
        className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
      >
        {saved ? "Saved!" : "Save Keys"}
      </button>
    </div>
  );
}
