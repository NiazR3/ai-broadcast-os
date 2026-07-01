import { useState, useEffect } from "react";
import type { DragEvent } from "react";
import {
  listPersonas, deletePersona,
  assignHostPersona, removeHostPersona,
  assignCoHostPersona, removeCoHostPersona,
  duplicatePersona, reorderPersonas,
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
  const [loading, setLoading] = useState(true);

  const fetchPersonas = async () => {
    try {
      setPersonas(await listPersonas());
    } catch {
      setError("Failed to load personas");
    }
  };

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      await fetchPersonas();
      setLoading(false);
    };
    load();
  }, []);

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
        ? prev.filter(x => x !== id)
        : [...prev, id]
    );
  };

  const handleDeleteSelected = async () => {
    setError(null);
    try {
      for (const id of selectedIds) {
        await deletePersona(id);
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
      for (const id of selectedIds) {
        await duplicatePersona(id);
      }
      await fetchPersonas();
    } catch {
      setError("Failed to duplicate selected personas");
    }
  };

  const handleAssignToHost = async () => {
    setError(null);
    try {
      for (const id of selectedIds) {
        await assignHostPersona(id);
      }
      await fetchPersonas();
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

  const handleDrop = async (index: number) => {
    if (dragIndex === null || dragIndex === index) return;

    const newPersonasOrder = [...personas];
    const [removed] = newPersonasOrder.splice(dragIndex!, 1);
    newPersonasOrder.splice(index, 0, removed);

    setPersonas(newPersonasOrder);

    try {
      await reorderPersonas(newPersonasOrder.map(p => p.id));
    } catch (err) {
      setError("Failed to reorder personas");
      fetchPersonas();
    } finally {
      setDragIndex(null);
    }
  };

  const getHealthStatus = (persona: PersonaProfile): { text: string; color: string } => {
    if (hostPersonaId === persona.id) {
      return { text: "Assigned (Host)", color: "text-green-700" };
    }
    if (cohostPersonaId === persona.id) {
      return { text: "Assigned (Co-Host)", color: "text-purple-700" };
    }

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

  const healthBadge = (persona: PersonaProfile): string => {
    if (hostPersonaId === persona.id) return "badge--brand";
    if (cohostPersonaId === persona.id) return "badge--info";
    const hasName = !!persona.name?.trim();
    const hasTraits = persona.personality_traits.length > 0;
    const hasCatchphrases = persona.catchphrases.length > 0;
    const hasEmotions = persona.emotional_range.length > 0;
    const hasBackground = !!persona.background_story?.trim();
    const completeness = (
      (hasName ? 1 : 0) + (hasTraits ? 1 : 0) +
      (hasCatchphrases ? 1 : 0) + (hasEmotions ? 1 : 0) +
      (hasBackground ? 1 : 0)
    ) / 5;
    if (completeness >= 0.8) return "badge--live";
    if (completeness >= 0.5) return "badge--warning";
    return "badge--danger";
  };

  return (
    <div className="space-y-5">
      {/* ── Section Header ── */}
      <div className="section-header">
        <div>
          <h3 className="section-header__title">Persona Profiles</h3>
          <p className="section-header__subtitle">
            Manage AI personalities for your broadcast
            {selectedIds.length > 0 && (
              <span className="ml-2 text-brand">
                &middot; {selectedIds.length} selected
              </span>
            )}
          </p>
        </div>
        <div className="section-header__actions">
          {selectedIds.length > 0 && (
            <>
              <button onClick={handleDuplicateSelected} className="btn btn-ghost btn--sm">
                Duplicate
              </button>
              <button onClick={handleDeleteSelected} className="btn btn-danger btn--sm">
                Delete Selected
              </button>
            </>
          )}
          <button onClick={() => setShowNew(true)} className="btn btn-primary btn--sm">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            New Persona
          </button>
        </div>
      </div>

      {/* ── Error Banner ── */}
      {error && (
        <div className="animate-fade-in-down flex items-center gap-2.5 rounded-lg border border-danger/30 bg-danger-bg px-4 py-3 text-sm text-danger" role="alert">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0" aria-hidden="true">
            <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          {error}
        </div>
      )}

      {/* ── Assignment Status ── */}
      <div className="flex items-center gap-4">
        <span className="flex items-center gap-1.5 text-xs">
          <span className="inline-block h-2 w-2 rounded-full bg-brand" />
          <span className="text-text-secondary">Host:</span>
          <span className={hostPersonaId ? "font-medium text-text" : "text-text-muted"}>
            {hostPersonaId ? personas.find(p => p.id === hostPersonaId)?.name ?? "Assigned" : "Default"}
          </span>
        </span>
        <span className="flex items-center gap-1.5 text-xs">
          <span className="inline-block h-2 w-2 rounded-full bg-info" />
          <span className="text-text-secondary">Co-Host:</span>
          <span className={cohostPersonaId ? "font-medium text-text" : "text-text-muted"}>
            {cohostPersonaId ? personas.find(p => p.id === cohostPersonaId)?.name ?? "Assigned" : "Default"}
          </span>
        </span>
      </div>

      {/* ── Bulk Action Bar ── */}
      {personas.length > 0 && (
        <div className="card card--elevated flex items-center gap-4 px-4 py-3">
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={selectedIds.length === personas.length && personas.length > 0}
              onChange={handleSelectAll}
              className="h-4 w-4 rounded border-border bg-bg-base text-brand focus:ring-2 focus:ring-brand/50"
            />
            <span className="text-sm font-medium text-text-secondary select-none">Select All</span>
          </label>
          <span className="flex-1 text-right text-xs text-text-muted">
            <span className="data-value">{selectedIds.length}</span> of{" "}
            <span className="data-value">{personas.length}</span> selected
          </span>
          {selectedIds.length > 0 && (
            <button onClick={handleAssignToHost} className="btn btn-ghost btn--sm">
              Assign to All Hosts
            </button>
          )}
        </div>
      )}

      {/* ── Persona List ── */}
      <div className="space-y-2">
        {loading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="card space-y-3" aria-hidden="true">
              <div className="flex items-start gap-3">
                <div className="h-3 w-3 shrink-0 rounded-full bg-border animate-pulse" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-40 rounded bg-border animate-pulse" />
                  <div className="h-3 w-64 rounded bg-border animate-pulse" />
                </div>
                <div className="flex gap-2">
                  <div className="h-6 w-16 rounded bg-border animate-pulse" />
                  <div className="h-6 w-14 rounded bg-border animate-pulse" />
                </div>
              </div>
            </div>
          ))
        ) : personas.length === 0 ? (
          <div className="card py-10 text-center">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mx-auto mb-3 text-text-muted" aria-hidden="true">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
            <p className="text-sm text-text-muted">
              No personas yet. Create one to customize how your agents sound.
            </p>
          </div>
        ) : (
          personas.map((p, index) => {
            const health = getHealthStatus(p);
            const badgeClass = healthBadge(p);
            const isHost = hostPersonaId === p.id;
            const isCoHost = cohostPersonaId === p.id;
            const isDragOver = dragIndex === index;

            return (
              <div
                key={p.id}
                draggable={true}
                className={`card transition-all duration-150 ${
                  isDragOver ? "opacity-50" : ""
                } ${
                  selectedIds.includes(p.id)
                    ? "border-brand/40"
                    : "card--interactive"
                }`}
                onDragStart={() => handleDragStart(index)}
                onDragOver={(e) => handleDragOver(e)}
                onDrop={() => handleDrop(index)}
              >
                <div className="flex items-start justify-between gap-3">
                  {/* Drag handle + dot indicator + info */}
                  <div className="flex min-w-0 flex-1 items-start gap-3">
                    {/* Drag handle */}
                    <div className="mt-0.5 shrink-0 cursor-grab text-text-muted active:cursor-grabbing" title="Drag to reorder" aria-label="Drag to reorder" role="img">
                      <svg width="12" height="16" viewBox="0 0 12 16" fill="currentColor" aria-hidden="true">
                        <circle cx="3" cy="3" r="1.5" /><circle cx="9" cy="3" r="1.5" />
                        <circle cx="3" cy="8" r="1.5" /><circle cx="9" cy="8" r="1.5" />
                        <circle cx="3" cy="13" r="1.5" /><circle cx="9" cy="13" r="1.5" />
                      </svg>
                    </div>

                    {/* Role dot */}
                    <div className="shrink-0">
                      <div
                        className={`h-3 w-3 rounded-full ${
                          isHost ? "bg-brand" : isCoHost ? "bg-info" : "bg-text-muted"
                        }`}
                        aria-label={isHost ? "Host" : isCoHost ? "Co-Host" : "Unassigned"}
                      />
                    </div>

                    {/* Persona info */}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-text">{p.name}</p>
                      <p className="mt-0.5 truncate text-xs text-text-secondary">
                        {p.agent_type}
                        <span className="mx-1">&middot;</span>
                        {p.voice_style}
                        {p.personality_traits.length > 0 && (
                          <>
                            <span className="mx-1">&middot;</span>
                            {p.personality_traits.join(", ")}
                          </>
                        )}
                      </p>
                    </div>
                  </div>

                  {/* Right side: badge + actions */}
                  <div className="flex shrink-0 items-center gap-2">
                    <span className={`badge ${badgeClass}`}>{health.text}</span>
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(p.id)}
                      onChange={() => handleToggleSelect(p.id)}
                      className="h-4 w-4 rounded border-border bg-bg-base text-brand focus:ring-2 focus:ring-brand/50"
                      aria-label={`Select ${p.name}`}
                    />
                    <button onClick={() => setEditing(p)} className="btn btn-ghost btn--sm" aria-label="Edit persona">
                      Edit
                    </button>
                    <button onClick={() => handleDelete(p)} className="btn btn-ghost btn--sm text-danger hover:bg-danger-bg" aria-label="Delete persona">
                      Del
                    </button>
                  </div>
                </div>

                {/* Catchphrases + Emotions */}
                <div className="mt-2 space-y-0.5 pl-7">
                  {p.catchphrases.length > 0 && (
                    <p className="truncate text-xs italic text-text-muted">
                      &ldquo;{p.catchphrases.join(", ")}&rdquo;
                    </p>
                  )}
                  {p.emotional_range.length > 0 && (
                    <p className="truncate text-xs text-text-muted">
                      Emotions: {p.emotional_range.join(", ")}
                    </p>
                  )}
                </div>

                {/* Assignment buttons */}
                <div className="mt-3 flex gap-2 pl-7">
                  {isHost ? (
                    <button onClick={handleRemoveHost}
                      className="btn btn-ghost btn--sm text-accent hover:bg-accent-bg">
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent" />
                      Unassign Host
                    </button>
                  ) : (
                    <button onClick={() => handleAssignHost(p.id)}
                      className="btn btn-ghost btn--sm text-brand hover:bg-brand/10">
                      Assign to Host
                    </button>
                  )}
                  {isCoHost ? (
                    <button onClick={handleRemoveCoHost}
                      className="btn btn-ghost btn--sm text-accent hover:bg-accent-bg">
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent" />
                      Unassign Co-Host
                    </button>
                  ) : (
                    <button onClick={() => handleAssignCoHost(p.id)}
                      className="btn btn-ghost btn--sm text-info hover:bg-info/10">
                      Assign to Co-Host
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* ── Editor Modals ── */}
      {showNew && <PersonaEditor persona={null} onSave={() => { setShowNew(false); fetchPersonas(); }} onCancel={() => setShowNew(false)} />}
      {editing && <PersonaEditor persona={editing} onSave={() => { setEditing(null); fetchPersonas(); }} onCancel={() => setEditing(null)} />}
    </div>
  );
}
