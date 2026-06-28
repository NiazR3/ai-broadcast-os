import { useState } from "react";

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

  const handleSave = async () => {
    try {
      const res = await fetch("http://localhost:8100/broadcast/platforms", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(keys),
      });
      if (res.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      }
    } catch {
      // ignore
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
      <button
        onClick={handleSave}
        className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
      >
        {saved ? "Saved!" : "Save Keys"}
      </button>
    </div>
  );
}
