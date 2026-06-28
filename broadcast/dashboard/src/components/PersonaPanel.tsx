import { useState, useEffect, useMemo } from "react";
import {
  listPersonas, deletePersona, duplicatePersona,
  assignHostPersona, removeHostPersona,
  assignCoHostPersona, removeCoHostPersona,
} from "../lib/api";
import type { PersonaProfile } from "../lib/api";
import { PersonaEditor } from "./PersonaEditor";

type SortField = "name" | "agent_type" | "voice_style";
type SortDir = "asc" | "desc";

export function PersonaPanel() {
  const [personas, setPersonas] = useState<PersonaProfile[]>([]);
  const [editing, setEditing] = useState<PersonaProfile | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [hostPersonaId, setHostPersonaId] = useState<string | null>(null);
  const [cohostPersonaId, setCohostPersonaId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [sortField, setSortField] = useState<SortField>("name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const fetchPersonas = async () => {
    try {
      setPersonas(await listPersonas());
    } catch {
      setError("Failed to load personas");
    }
  };

  useEffect(() => { fetchPersonas(); }, []);

  // ── Derived state ──────────────────────────────────────────────

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return personas.filter(p =>
      p.name.toLowerCase().includes(q) ||
      p.agent_type.toLowerCase().includes(q) ||
      p.voice_style.toLowerCase().includes(q) ||
      p.personality_traits.some(t => t.toLowerCase().includes(q))
    );
  }, [personas, search]);

  const sorted = useMemo(() => {
    const copy = [...filtered];
    copy.sort((a, b) => {
      const va = String(a[sortField] ?? "");
      const vb = String(b[sortField] ?? "");
      const cmp = va.localeCompare(vb);
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [filtered, sortField, sortDir]);

  const allSelected = sorted.length > 0 && sorted.every(p => selected.has(p.id));

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(d => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  };

  // ── Handlers ───────────────────────────────────────────────────

  const handleDelete = async (p: PersonaProfile) => {
    setError(null);
    try {
      await deletePersona(p.id);
      if (hostPersonaId === p.id) setHostPersonaId(null);
      if (cohostPersonaId === p.id) setCohostPersonaId(null);
      setSelected(prev => { const next = new Set(prev); next.delete(p.id); return next; });
      await fetchPersonas();
    } catch {
      setError("Failed to delete (persona may be assigned)");
    }
  };

  const handleDuplicate = async (p: PersonaProfile) => {
    setError(null);
    try {
      await duplicatePersona(p.id);
      await fetchPersonas();
    } catch {
      setError("Failed to duplicate persona");
    }
  };

  const handleBulkDelete = async () => {
    setError(null);
    let failed = false;
    for (const id of selected) {
      try {
        await deletePersona(id);
        if (hostPersonaId === id) setHostPersonaId(null);
        if (cohostPersonaId === id) setCohostPersonaId(null);
      } catch {
        failed = true;
      }
    }
    if (failed) setError("Some personas could not be deleted (may be assigned)");
    setSelected(new Set());
    await fetchPersonas();
  };

  const handleBulkAssignHost = async () => {
    setError(null);
    for (const id of selected) {
      try {
        await assignHostPersona(id);
        if (hostPersonaId !== id) setHostPersonaId(id);
      } catch { /* skip failures */ }
    }
    setSelected(new Set());
  };

  const handleSelectAll = () => {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(sorted.map(p => p.id)));
    }
  };

  const toggleSelected = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
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

  // ── Helpers ────────────────────────────────────────────────────

  const statusBadge = (p: PersonaProfile) => {
    if (p.id === hostPersonaId) return <span className="px-1.5 py-0.5 text-[10px] font-medium bg-green-100 text-green-700 rounded-full">🟢 Active</span>;
    if (p.id === cohostPersonaId) return <span className="px-1.5 py-0.5 text-[10px] font-medium bg-purple-100 text-purple-700 rounded-full">🟣 Assigned</span>;
    return <span className="px-1.5 py-0.5 text-[10px] font-medium bg-gray-100 text-gray-500 rounded-full">⚪ Idle</span>;
  };

  const sortIndicator = (field: SortField) => {
    if (sortField !== field) return " ↕";
    return sortDir === "asc" ? " ↑" : " ↓";
  };

  // ── Render ─────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Header */}
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

      {/* Search + Bulk actions */}
      <div className="flex gap-2 items-center">
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search personas..."
          className="flex-1 px-3 py-1.5 border rounded text-sm"
        />
        {selected.size > 0 && (
          <div className="flex gap-1">
            <span className="text-xs text-gray-500 self-center">{selected.size} selected</span>
            <button onClick={handleBulkAssignHost}
              className="px-2 py-1 text-xs bg-blue-50 text-blue-700 rounded hover:bg-blue-100">
              Assign to Host
            </button>
            <button onClick={handleBulkDelete}
              className="px-2 py-1 text-xs bg-red-50 text-red-700 rounded hover:bg-red-100">
              Delete
            </button>
          </div>
        )}
      </div>

      {/* Sort + column headers */}
      <div className="flex gap-4 text-xs text-gray-500 px-2">
        <button onClick={handleSelectAll} className="w-5 text-center" title={allSelected ? "Deselect all" : "Select all"}>
          {allSelected ? "☑" : "☐"}
        </button>
        <button onClick={() => toggleSort("name")} className="flex-1 text-left font-medium hover:text-gray-800">
          Name{sortIndicator("name")}
        </button>
        <button onClick={() => toggleSort("agent_type")} className="w-20 text-left font-medium hover:text-gray-800">
          Type{sortIndicator("agent_type")}
        </button>
        <button onClick={() => toggleSort("voice_style")} className="w-24 text-left font-medium hover:text-gray-800">
          Voice{sortIndicator("voice_style")}
        </button>
        <span className="w-16 text-center">Status</span>
        <span className="w-32 text-right">Actions</span>
      </div>

      {/* Persona list */}
      <div className="space-y-1">
        {sorted.map(p => (
          <div
            key={p.id}
            className={`border rounded px-3 py-2 flex gap-4 items-center text-sm transition-colors ${
              selected.has(p.id) ? "border-blue-400 bg-blue-50" : "hover:border-gray-300"
            }`}
          >
            {/* Checkbox */}
            <button onClick={() => toggleSelected(p.id)} className="w-5 text-center text-gray-400 hover:text-gray-600">
              {selected.has(p.id) ? "☑" : "☐"}
            </button>

            {/* Details */}
            <div className="flex-1 min-w-0">
              <p className="font-medium truncate">{p.name}</p>
              {p.personality_traits.length > 0 && (
                <p className="text-xs text-gray-500 truncate">
                  {p.personality_traits.join(", ")}
                </p>
              )}
            </div>

            {/* Type */}
            <span className="w-20 text-xs text-gray-500 capitalize">{p.agent_type}</span>

            {/* Voice */}
            <span className="w-24 text-xs text-gray-500 capitalize">{p.voice_style}</span>

            {/* Status badge */}
            <div className="w-16 flex justify-center">{statusBadge(p)}</div>

            {/* Actions */}
            <div className="w-32 flex gap-1 justify-end shrink-0">
              <button onClick={() => handleDuplicate(p)}
                className="px-2 py-0.5 text-xs border rounded hover:bg-gray-50"
                title="Duplicate persona">
                📋
              </button>
              <button onClick={() => setEditing(p)}
                className="px-2 py-0.5 text-xs border rounded hover:bg-gray-50">
                Edit
              </button>
              {hostPersonaId === p.id ? (
                <button onClick={handleRemoveHost}
                  className="px-2 py-0.5 text-xs bg-orange-100 text-orange-700 rounded hover:bg-orange-200">
                  Unassign
                </button>
              ) : (
                <>
                  <button onClick={() => handleAssignHost(p.id)}
                    className="px-2 py-0.5 text-xs bg-blue-50 text-blue-700 rounded hover:bg-blue-100">
                    Host
                  </button>
                  <button onClick={() => handleAssignCoHost(p.id)}
                    className="px-2 py-0.5 text-xs bg-purple-50 text-purple-700 rounded hover:bg-purple-100">
                    Co-Host
                  </button>
                </>
              )}
              <button onClick={() => handleDelete(p)}
                className="px-2 py-0.5 text-xs border rounded text-red-600 hover:bg-red-50">
                ✕
              </button>
            </div>
          </div>
        ))}
        {sorted.length === 0 && (
          <p className="text-xs text-gray-400 text-center py-4">
            {search ? "No personas match your search." : "No personas yet. Create one to customize how your agents sound."}
          </p>
        )}
      </div>

      {/* Editor modals */}
      {showNew && <PersonaEditor persona={null} onSave={() => { setShowNew(false); fetchPersonas(); }} onCancel={() => setShowNew(false)} />}
      {editing && <PersonaEditor persona={editing} onSave={() => { setEditing(null); fetchPersonas(); }} onCancel={() => setEditing(null)} />}
    </div>
  );
}
