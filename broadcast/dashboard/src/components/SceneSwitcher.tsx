import { useState, useEffect } from "react";
import { getScenes, switchScene } from "../lib/api";

export function SceneSwitcher() {
  const [scenes, setScenes] = useState<string[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getScenes()
      .then(setScenes)
      .catch(() => setError("OBS not connected"));
  }, []);

  const handleSwitch = async (name: string) => {
    try {
      await switchScene(name);
      setActive(name);
      setError(null);
    } catch {
      setError("Failed to switch scene");
    }
  };

  if (error) {
    return (
      <div className="p-4 bg-yellow-50 rounded-lg border border-yellow-200">
        <p className="text-yellow-700 text-sm">{error}</p>
      </div>
    );
  }

  return (
    <div>
      <h3 className="font-semibold mb-3">Scenes</h3>
      <div className="flex flex-wrap gap-2">
        {scenes.map((scene) => (
          <button
            key={scene}
            onClick={() => handleSwitch(scene)}
            className={`px-4 py-2 rounded border text-sm transition-colors ${
              active === scene
                ? "bg-blue-600 text-white border-blue-600"
                : "bg-white text-gray-700 border-gray-300 hover:bg-gray-100"
            }`}
          >
            {scene}
          </button>
        ))}
      </div>
    </div>
  );
}
