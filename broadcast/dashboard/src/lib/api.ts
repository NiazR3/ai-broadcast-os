export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8100";

export interface PlatformStatus {
  streaming: boolean;
  rtmp_url: string;
  error: string | null;
}

export interface BroadcastStatus {
  active: boolean;
  uptime_seconds: number;
  platforms: Record<string, PlatformStatus>;
}

export interface BroadcastEvent {
  type: string;
  timestamp: number;
  scene?: string;
  platform?: string;
  error?: string;
}

export async function getStatus(): Promise<BroadcastStatus> {
  const res = await fetch(`${API_BASE}/broadcast/status`);
  if (!res.ok) throw new Error("Failed to fetch status");
  return res.json();
}

export async function startBroadcast(): Promise<BroadcastStatus> {
  const res = await fetch(`${API_BASE}/broadcast/start`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to start broadcast");
  return res.json();
}

export async function stopBroadcast(): Promise<BroadcastStatus> {
  const res = await fetch(`${API_BASE}/broadcast/stop`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to stop broadcast");
  return res.json();
}

export async function getScenes(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/broadcast/scenes`);
  if (!res.ok) throw new Error("Failed to fetch scenes");
  const data = await res.json();
  return data.scenes;
}

export async function switchScene(name: string): Promise<void> {
  const res = await fetch(`${API_BASE}/broadcast/scenes/${encodeURIComponent(name)}`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to switch scene");
}

// ── Agent API types ──────────────────────────────────────────
export interface DialogueLine {
  speaker: string;
  text: string;
  emotion?: string;
  order: number;
}

export interface DialogueBlock {
  segment_id: string;
  lines: DialogueLine[];
}

export interface Segment {
  id: string;
  type: string;
  title: string;
  duration_seconds: number;
  scene_name: string;
  dialogue_prompt: string;
  order: number;
}

export interface EpisodeScript {
  id: string;
  title: string;
  segments: Segment[];
  status: string;
  total_duration: number;
}

export interface DirectorStatus {
  running: boolean;
  current_segment: Segment | null;
  current_segment_index: number | null;
  has_more: boolean;
  script_loaded: boolean;
  script_title: string | null;
}

// ── Agent API functions ──────────────────────────────────────
export async function createEpisode(title: string): Promise<EpisodeScript> {
  const res = await fetch(`${API_BASE}/agent/episode`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error("Failed to create episode");
  return res.json();
}

export async function listEpisodes(): Promise<EpisodeScript[]> {
  const res = await fetch(`${API_BASE}/agent/episodes`);
  if (!res.ok) throw new Error("Failed to list episodes");
  return res.json();
}

export async function addSegment(episodeId: string, segment: Partial<Segment>): Promise<EpisodeScript> {
  const res = await fetch(`${API_BASE}/agent/episode/${episodeId}/segment`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(segment),
  });
  if (!res.ok) throw new Error("Failed to add segment");
  return res.json();
}

export async function loadEpisode(episodeId: string): Promise<{ loaded: boolean; title: string; segment_count: number }> {
  const res = await fetch(`${API_BASE}/agent/episode/${episodeId}/load`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to load episode");
  return res.json();
}

export async function getDirectorStatus(): Promise<DirectorStatus> {
  const res = await fetch(`${API_BASE}/agent/director/status`);
  if (!res.ok) throw new Error("Failed to get director status");
  return res.json();
}

export async function directorNext(): Promise<{ segment: Segment; segment_index: number; has_more: boolean }> {
  const res = await fetch(`${API_BASE}/agent/director/next`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to advance segment");
  return res.json();
}

export async function generateDialogue(): Promise<{ segment_id: string; host: DialogueBlock; cohost: DialogueBlock }> {
  const res = await fetch(`${API_BASE}/agent/director/generate`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to generate dialogue");
  return res.json();
}

export async function hostDialogue(segment: Partial<Segment>): Promise<DialogueBlock> {
  const res = await fetch(`${API_BASE}/agent/host/dialogue`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(segment),
  });
  if (!res.ok) throw new Error("Failed to generate host dialogue");
  return res.json();
}

export async function cohostDialogue(segment: Partial<Segment>): Promise<DialogueBlock> {
  const res = await fetch(`${API_BASE}/agent/cohost/dialogue`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(segment),
  });
  if (!res.ok) throw new Error("Failed to generate co-host dialogue");
  return res.json();
}
