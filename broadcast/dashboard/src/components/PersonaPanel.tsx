import { useState, useEffect, CallbackRef, DragEvent } from "react";
import {
  listPersonas, deletePersona,
  assignHostPersona, removeHostPersona,
  assignCoHostPersona, removeCoHostPersona,
  duplicatePersona,
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
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [dragIndex, setDragIndex] = useState<number | null>(null);

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

  const handleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      setSelectedIds(personas.map(p => p.id));
    } else {
      setSelectedIds([]);
    }
  };

  const handleToggleSelect = (id: string) => {
    setSelectedIds(prev =>
      prev.includes(id)
        ? prev.filter(id => id !== id)
        : [...prev, id]
    );
  };

  const handleDeleteSelected = async () => {
    setError(null);
    try {
      // Delete selected personas one by one
      for (const id of selectedIds) {
        await deletePersona(id);

        // Update assigned persona IDs if needed
        if (hostPersonaId === id) setHostPersonaId(null);
        if (cohostPersonaId === id) setCohostPersonaId(null);
      }

      setSelectedIds([]);
      await fetchPersonas();
    } catch {
      setError("Failed to delete selected personas");
    }
  };

  const handleDuplicateSelected = async () => {
    setError(null);
    try {
      // Duplicate selected personas one by one
      for (const id of selectedIds) {
        await duplicatePersona(id);
      }

      await fetchPersonas();
    } catch {
      setError("Failed to duplicate selected personas");
    }
  };

  const handleAssignAllToHost = async () => {
    setError(null);
    try {
      // Assign all selected personas to host (one at a time)
      for (const id of selectedIds) {
        await assignHostPersona(id);
      }
      // Set the last selected persona as the host (or we could set the first one)
      // For simplicity, we'll just fetch personas to update the UI
      await fetchPersonas();

      // Clear selection after assignment
      setSelectedIds([]);
    } catch {
      setError("Failed to assign selected personas to host");
    }
  };

  const handleDragStart = (index: number) => {
    setDragIndex(index);
  };

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (index: number) => {
    if (dragIndex === null || dragIndex === index) return;

    setPersonas(prev => {
      const newArray = [...prev];
      const [removed] = newArray.splice(dragIndex!, 1);
      newArray.splice(index, 0, removed);
      return newArray;
    });

    setDragIndex(null);
  };

  const getHealthStatus = (persona: PersonaProfile): { text: string; color: string } => {
    // Check if persona is assigned to host or co-host
    if (hostPersonaId === persona.id) {
      return { text: "Assigned (Host)", color: "text-green-700" };
    }
    if (cohostPersonaId === persona.id) {
      return { text: "Assigned (Co-Host)", color: "text-purple-700" };
    }

    // Check if persona has essential fields filled
    const hasName = !!persona.name?.trim();
    const hasTraits = persona.personality_traits.length > 0;
    const hasCatchphrases = persona.catchphrases.length > 0;
    const hasEmotions = persona.emotional_range.length > 0;
    const hasBackground = !!persona.background_story?.trim();

    const completeness = (
      (hasName ? 1 : 0) +
      (hasTraits ? 1 : 0) +
      (hasCatchphrases ? 1 : 0) +
      (hasEmotions ? 1 : 0) +
      (hasBackground ? 1 : 0)
    ) / 5;

    if (completeness >= 0.8) {
      return { text: "Healthy", color: "text-green-600" };
    } else if (completeness >= 0.5) {
      return { text: "Needs Work", color: "text-yellow-600" };
    } else {
      return { text: "Incomplete", color: "text-red-600" };
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div className="flex flex-col">
          <h3 className="font-semibold">Persona Profiles</h3>
          {selectedIds.length > 0 && (
            <span className="text-xs text-blue-600 mt-1">
              {selectedIds.length} selected
            </span>
          )}
        </div>
        <div className="flex space-x-2">
          <button onClick={() => setShowNew(true)}
            className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">
            + New Persona
          </button>
          {selectedIds.length > 0 && (
            <>
              <button onClick={handleDuplicateSelected}
                className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50"
                disabled={selectedIds.length === 0}>
                Duplicate
              </button>
              <button onClick={handleDeleteSelected}
                className="px-3 py-1.5 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50"
                disabled={selectedIds.length === 0}>
                Delete Selected
              </button>
            </>
          )}
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {/* Bulk actions */}
      {personas.length > 0 && (
        <div className="flex items-center space-x-4 p-3 bg-gray-50 rounded mb-4">
          <div className="flex items-center">
            <input
              type="checkbox"
              checked={selectedIds.length === personas.length && personas.length > 0}
              onChange={handleSelectAll}
              className="h-4 w-4 text-blue-600"
            />
            <span className="ml-2 text-sm font-medium">Select All</span>
          </div>
          <div className="flex-1 text-right text-sm text-gray-500">
            {selectedIds.length} of {personas.length} selected
          </div>
          {selectedIds.length > 0 && (
            <button onClick={handleAssignAllToHost}
              className="px-3 py-1.5 bg-indigo-600 text-white rounded text-sm hover:bg-indigo-700 disabled:opacity-50"
              disabled={selectedIds.length === 0}>
              Assign to All Hosts
            </button>
          )}
        </div>
      )}

      {/* Assignment status */}
      <div className="flex gap-4 text-xs">
        <span className={hostPersonaId ? "text-green-700" : "text-gray-500"}>
          Host: {hostPersonaId ? personas.find(p => p.id === hostPersonaId)?.name ?? "Assigned" : "Default"}
        </span>
        <span className={cohostPersonaId ? "text-purple-700" : "text-gray-500"}>
          Co-Host: {cohostPersonaId ? personas.find(p => p.id === cohostPersonaId)?.name ?? "Assigned" : "Default"}
        </span>
      </div>

      {/* Persona list with drag-and-drop */}
      <div className="space-y-2">
        <div className="space-y-1">
          {personas.map((p, index) => (
            <div
              key={p.id}
              className={`border rounded p-3 space-y-1 hover:border-gray-400 transition-colors cursor-grab
                ${selectedIds.includes(p.id) ? "border-blue-300 bg-blue-50" : ""}
                ${dragIndex === index ? "opacity-50" : ""}`}
              onDragStart={() => handleDragStart(index)}
              onDragOver={(e) => handleDragOver(e)}
              onDrop={() => handleDrop(index)}
            >
              <div className="flex justify-between items-start">
                <div className="flex items-start space-x-3">
                  <div className="flex-shrink-0">
                    <div className={`w-3 h-3 rounded-full
                      ${hostPersonaId === p.id ? "bg-green-500" : ""}
                      ${cohostPersonaId === p.id ? "bg-purple-500" : ""}
                    `}" title={hostPersonaId === p.id ? "Host" : cohostPersonaId === p.id ? "Co-Host" : "Unassigned"}/>
                  </div>
                  <div>
                    <p className="font-medium text-sm">{p.name}</p>
                    <p className="text-xs text-gray-500">
                      {p.agent_type} · {p.voice_style}
                      {p.personality_traits.length > 0 && ` · ${p.personality_traits.join(", ")}`}
                    </p>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <div className={getHealthStatus(p).color}>
                    <span className="text-xs">{getHealthStatus(p).text}</span>
                  </div>
                  <div className="flex gap-1">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(p.id)}
                      onChange={() => handleToggleSelect(p.id)}
                      className="h-4 w-4 text-blue-600"
                    />
                    <button onClick={() => setEditing(p)}
                      className="px-2 py-0.5 text-xs border rounded hover:bg-gray-50">
                      Edit
                    </button>
                    <button onClick={() => handleDelete(p)}
                      className="px-2 py-0.5 text-xs border rounded text-red-600 hover:bg-red-50">
                      Delete
                    </button>
                  </div>
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
      </div>

      {/* Editor modals */}
      {showNew && <PersonaEditor persona={null} onSave={() => { setShowNew(false); fetchPersonas(); }} onCancel={() => setShowNew(false)} />}
      {editing && <PersonaEditor persona={editing} onSave={() => { setEditing(null); fetchPersonas(); }} onCancel={() => setEditing(null)} />}
    </div>
  );
}
