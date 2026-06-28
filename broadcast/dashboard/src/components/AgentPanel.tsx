import { useState, useEffect } from "react";
import {
  createEpisode, listEpisodes, addSegment,
  loadEpisode, getDirectorStatus, directorNext, generateDialogue,
} from "../lib/api";
import type { EpisodeScript, DirectorStatus } from "../lib/api";

export function AgentPanel() {
  const [episodes, setEpisodes] = useState<EpisodeScript[]>([]);
  const [director, setDirector] = useState<DirectorStatus | null>(null);
  const [title, setTitle] = useState("");
  const [segTitle, setSegTitle] = useState("");
  const [segType, setSegType] = useState("content");
  const [selectedEp, setSelectedEp] = useState<string | null>(null);
  const [dialogue, setDialogue] = useState<{ host: string; cohost: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchEpisodes = async () => {
    try { setEpisodes(await listEpisodes()); } catch { /* ignore */ }
  };
  const fetchDirector = async () => {
    try { setDirector(await getDirectorStatus()); } catch { /* ignore */ }
  };

  useEffect(() => { fetchEpisodes(); fetchDirector(); }, []);

  const handleCreate = async () => {
    if (!title.trim()) return;
    setError(null);
    try {
      await createEpisode(title.trim());
      setTitle("");
      await fetchEpisodes();
    } catch { setError("Failed to create episode"); }
  };

  const handleAddSegment = async () => {
    if (!selectedEp || !segTitle.trim()) return;
    setError(null);
    try {
      const id = `seg_${Date.now()}`;
      await addSegment(selectedEp, { id, type: segType, title: segTitle.trim(), duration_seconds: 30 });
      setSegTitle("");
      await fetchEpisodes();
    } catch { setError("Failed to add segment"); }
  };

  const handleLoad = async (epId: string) => {
    setError(null);
    try {
      await loadEpisode(epId);
      setSelectedEp(epId);
      await fetchDirector();
    } catch { setError("Failed to load episode"); }
  };

  const handleNext = async () => {
    setError(null);
    setDialogue(null);
    try {
      await directorNext();
      await fetchDirector();
    } catch { setError("No more segments"); }
  };

  const handleGenerate = async () => {
    setError(null);
    try {
      const d = await generateDialogue();
      setDialogue({
        host: d.host.lines.map(l => l.text).join(" "),
        cohost: d.cohost.lines.map(l => l.text).join(" "),
      });
    } catch { setError("Failed to generate dialogue"); }
  };

  return (
    <div className="space-y-4">
      <h3 className="font-semibold">Director Controls</h3>

      {/* Director Status */}
      {director && (
        <div className="text-sm space-y-1 p-3 bg-gray-50 rounded border">
          <p><strong>Status:</strong> {director.running ? "Running" : "Idle"}</p>
          <p><strong>Script:</strong> {director.script_title || "None loaded"}</p>
          <p><strong>Current segment:</strong> {director.current_segment?.title || "None"}</p>
          <p><strong>Remaining:</strong> {director.has_more ? "More segments" : "End of show"}</p>
        </div>
      )}

      {/* Controls */}
      <div className="flex gap-2">
        <button onClick={handleNext} className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">
          Next Segment
        </button>
        <button onClick={handleGenerate} className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700">
          Generate Dialogue
        </button>
      </div>

      {/* Dialogue Display */}
      {dialogue && (
        <div className="space-y-2 p-3 bg-white border rounded">
          <div className="border-l-4 border-blue-500 pl-3">
            <p className="text-xs font-semibold text-blue-700">Host</p>
            <p className="text-sm">{dialogue.host}</p>
          </div>
          <div className="border-l-4 border-purple-500 pl-3">
            <p className="text-xs font-semibold text-purple-700">Co-Host</p>
            <p className="text-sm">{dialogue.cohost}</p>
          </div>
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <hr className="my-2" />

      {/* Create Episode */}
      <div className="space-y-2">
        <h4 className="text-sm font-medium">New Episode</h4>
        <div className="flex gap-2">
          <input
            type="text" value={title} placeholder="Episode title..."
            onChange={e => setTitle(e.target.value)}
            className="flex-1 px-2 py-1.5 border rounded text-sm"
          />
          <button onClick={handleCreate} className="px-3 py-1.5 bg-gray-700 text-white rounded text-sm hover:bg-gray-800">
            Create
          </button>
        </div>
      </div>

      {/* Add Segment */}
      {selectedEp && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium">Add Segment</h4>
          <div className="flex gap-2">
            <select value={segType} onChange={e => setSegType(e.target.value)}
              className="px-2 py-1.5 border rounded text-sm">
              <option value="intro">Intro</option>
              <option value="content">Content</option>
              <option value="guest">Guest</option>
              <option value="ad">Ad</option>
              <option value="outro">Outro</option>
            </select>
            <input type="text" value={segTitle} placeholder="Segment title..."
              onChange={e => setSegTitle(e.target.value)}
              className="flex-1 px-2 py-1.5 border rounded text-sm" />
            <button onClick={handleAddSegment} className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm">
              Add
            </button>
          </div>
        </div>
      )}

      {/* Episode List */}
      <div className="space-y-1 max-h-48 overflow-y-auto">
        <h4 className="text-sm font-medium">Episodes</h4>
        {episodes.map(ep => (
          <div key={ep.id}
            className={`flex justify-between items-center p-2 rounded text-sm cursor-pointer ${
              selectedEp === ep.id ? "bg-blue-50 border border-blue-200" : "hover:bg-gray-50 border border-transparent"
            }`}
            onClick={() => handleLoad(ep.id)}>
            <div>
              <p className="font-medium">{ep.title}</p>
              <p className="text-xs text-gray-500">{ep.segments.length} segments · {ep.status}</p>
            </div>
            {selectedEp === ep.id && <span className="text-xs text-blue-600">Loaded</span>}
          </div>
        ))}
        {episodes.length === 0 && <p className="text-xs text-gray-400">No episodes yet. Create one above.</p>}
      </div>
    </div>
  );
}
