import { useState, useEffect } from "react";
import {
  listPersonas, deletePersona,
  assignHostPersona, removeHostPersona,
  assignCoHostPersona, removeCoHostPersona,
} from "../lib/api";
import type { PersonaProfile } from "../lib/api";
import { PersonaEditor } from "./PersonaEditor";

export function PersonaPanel() {
  const [personas, setPersonas] = useState<PersonaProfile[]>([]);
  const [editing, setEditing] = useState<PersonaProfile | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [hostPersonaId, setHostPersonaId] = useState<string | null>(null);
  const [cohostPersonaId, setCohostPersonaId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchPersonas = async () => {
    try {
      setPersonas(await listPersonas());
    } catch {
      setError("Failed to load personas");
    }
  };

  useEffect(() => { fetchPersonas(); }, []);

  const handleDelete = async (p: PersonaProfile) => {
    setError(null);
    try {
      await deletePersona(p.id);
      if (hostPersonaId === p.id) setHostPersonaId(null);
      if (cohostPersonaId === p.id) setCohostPersonaId(null);
      await fetchPersonas();
    } catch {
      setError("Failed to delete (persona may be assigned)");
    }
  };

  const handleAssignHost = async (id: string) => {
    setError(null);
    try {
      await assignHostPersona(id);
      setHostPersonaId(id);
    } catch {
      setError("Failed to assign host persona");
    }
  };

  const handleRemoveHost = async () => {
    setError(null);
    try {
      await removeHostPersona();
      setHostPersonaId(null);
    } catch {
      setError("Failed to remove host persona");
    }
  };

  const handleAssignCoHost = async (id: string) => {
    setError(null);
    try {
      await assignCoHostPersona(id);
      setCohostPersonaId(id);
    } catch {
      setError("Failed to assign co-host persona");
    }
  };

  const handleRemoveCoHost = async () => {
    setError(null);
    try {
      await removeCoHostPersona();
      setCohostPersonaId(null);
    } catch {
      setError("Failed to remove co-host persona");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="font-semibold">Persona Profiles</h3>
        <button onClick={() => setShowNew(true)}
          className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">
          + New Persona
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {/* Assignment status */}
      <div className="flex gap-4 text-xs">
        <span className={hostPersonaId ? "text-green-700" : "text-gray-500"}>
          Host: {hostPersonaId ? personas.find(p => p.id === hostPersonaId)?.name ?? "Assigned" : "Default"}
        </span>
        <span className={cohostPersonaId ? "text-purple-700" : "text-gray-500"}>
          Co-Host: {cohostPersonaId ? personas.find(p => p.id === cohostPersonaId)?.name ?? "Assigned" : "Default"}
        </span>
      </div>

      {/* Persona list */}
      <div className="space-y-2">
        {personas.map(p => (
          <div key={p.id} className="border rounded p-3 space-y-1 hover:border-gray-400 transition-colors">
            <div className="flex justify-between items-start">
              <div>
                <p className="font-medium text-sm">{p.name}</p>
                <p className="text-xs text-gray-500">
                  {p.agent_type} · {p.voice_style}
                  {p.personality_traits.length > 0 && ` · ${p.personality_traits.join(", ")}`}
                </p>
              </div>
              <div className="flex gap-1">
                <button onClick={() => setEditing(p)}
                  className="px-2 py-1 text-xs border rounded hover:bg-gray-50">Edit</button>
                <button onClick={() => handleDelete(p)}
                  className="px-2 py-1 text-xs border rounded text-red-600 hover:bg-red-50">Delete</button>
              </div>
            </div>

            {p.catchphrases.length > 0 && (
              <p className="text-xs text-gray-600 italic">
                Catchphrases: {p.catchphrases.join(", ")}
              </p>
            )}
            {p.emotional_range.length > 0 && (
              <p className="text-xs text-gray-500">
                Emotions: {p.emotional_range.join(", ")}
              </p>
            )}

            {/* Assignment buttons */}
            <div className="flex gap-2 mt-1">
              {hostPersonaId === p.id ? (
                <button onClick={handleRemoveHost}
                  className="px-2 py-0.5 text-xs bg-orange-100 text-orange-700 rounded hover:bg-orange-200">
                  Unassign Host
                </button>
              ) : (
                <button onClick={() => handleAssignHost(p.id)}
                  className="px-2 py-0.5 text-xs bg-blue-50 text-blue-700 rounded hover:bg-blue-100">
                  Assign to Host
                </button>
              )}
              {cohostPersonaId === p.id ? (
                <button onClick={handleRemoveCoHost}
                  className="px-2 py-0.5 text-xs bg-orange-100 text-orange-700 rounded hover:bg-orange-200">
                  Unassign Co-Host
                </button>
              ) : (
                <button onClick={() => handleAssignCoHost(p.id)}
                  className="px-2 py-0.5 text-xs bg-purple-50 text-purple-700 rounded hover:bg-purple-100">
                  Assign to Co-Host
                </button>
              )}
            </div>
          </div>
        ))}
        {personas.length === 0 && (
          <p className="text-xs text-gray-400 text-center py-4">
            No personas yet. Create one to customize how your agents sound.
          </p>
        )}
      </div>

      {/* Editor modals */}
      {showNew && <PersonaEditor persona={null} onSave={() => { setShowNew(false); fetchPersonas(); }} onCancel={() => setShowNew(false)} />}
      {editing && <PersonaEditor persona={editing} onSave={() => { setEditing(null); fetchPersonas(); }} onCancel={() => setEditing(null)} />}
    </div>
  );
}
