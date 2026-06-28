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

// ── Persona API types ──────────────────────────────────────────
export interface PersonaProfile {
  id: string;
  name: string;
  agent_type: "host" | "cohost" | "director" | "producer";
  personality_traits: string[];
  catchphrases: string[];
  voice_style: "energetic" | "calm" | "professional" | "casual" | "witty" | "serious";
  default_emotion: string;
  emotional_range: string[];
  background_story: string;
}

// ── Persona API functions ──────────────────────────────────────
export async function listPersonas(): Promise<PersonaProfile[]> {
  const res = await fetch(`${API_BASE}/agent/personas`);
  if (!res.ok) throw new Error("Failed to list personas");
  return res.json();
}

export async function createPersona(data: Partial<PersonaProfile>): Promise<PersonaProfile> {
  const res = await fetch(`${API_BASE}/agent/personas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to create persona");
  return res.json();
}

export async function getPersona(id: string): Promise<PersonaProfile> {
  const res = await fetch(`${API_BASE}/agent/personas/${id}`);
  if (!res.ok) throw new Error("Failed to get persona");
  return res.json();
}

export async function updatePersona(id: string, data: Partial<PersonaProfile>): Promise<PersonaProfile> {
  const res = await fetch(`${API_BASE}/agent/personas/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to update persona");
  return res.json();
}

export async function deletePersona(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/agent/personas/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete persona");
}

export async function assignHostPersona(personaId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/agent/host/persona/${personaId}`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to assign host persona");
}

export async function removeHostPersona(): Promise<void> {
  const res = await fetch(`${API_BASE}/agent/host/persona`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to remove host persona");
}

export async function assignCoHostPersona(personaId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/agent/cohost/persona/${personaId}`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to assign co-host persona");
}

export async function removeCoHostPersona(): Promise<void> {
  const res = await fetch(`${API_BASE}/agent/cohost/persona`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to remove co-host persona");
}

// ── Audience API types ────────────────────────────────────────────────
export interface ChatMessage {
  id: string;
  platform: string;
  user: { id: string; display_name: string; platform: string; role: string; badges: string[] };
  text: string;
  timestamp: number;
  moderated: boolean;
  moderation_action: string | null;
}

export interface ModerationRule {
  id: string;
  pattern: string;
  action: string;
  reason: string;
  enabled: boolean;
  created_at: number;
}

export interface Poll {
  id: string;
  question: string;
  options: { text: string; votes: number }[];
  status: "pending" | "active" | "closed";
  duration_seconds: number;
  created_at: number;
  closed_at: number | null;
}

export interface AudienceStats {
  total_messages: number;
  unique_users: number;
  messages_per_minute: number;
  top_chatters: { user: string; count: number }[];
}

// ── Audience API functions ────────────────────────────────────────────

export async function getChat(limit = 50, flagged = false): Promise<ChatMessage[]> {
  const params = new URLSearchParams({ limit: String(limit), flagged: String(flagged) });
  const res = await fetch(`${API_BASE}/audience/chat?${params}`);
  if (!res.ok) throw new Error("Failed to fetch chat");
  return res.json();
}

export async function injectChat(text: string, userName = "TestUser", platform = "mock"): Promise<ChatMessage> {
  const res = await fetch(`${API_BASE}/audience/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, user_name: userName, platform }),
  });
  if (!res.ok) throw new Error("Failed to inject chat");
  return res.json();
}

export async function flagMessage(messageId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/audience/chat/${messageId}/flag`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to flag message");
}

export async function moderateMessage(messageId: string, action: string): Promise<void> {
  const res = await fetch(`${API_BASE}/audience/chat/${messageId}/moderate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
  if (!res.ok) throw new Error("Failed to moderate message");
}

export async function getModerationRules(): Promise<ModerationRule[]> {
  const res = await fetch(`${API_BASE}/audience/moderation/rules`);
  if (!res.ok) throw new Error("Failed to fetch rules");
  return res.json();
}

export async function createModerationRule(pattern: string, action = "flag", reason = ""): Promise<ModerationRule> {
  const res = await fetch(`${API_BASE}/audience/moderation/rules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pattern, action, reason }),
  });
  if (!res.ok) throw new Error("Failed to create rule");
  return res.json();
}

export async function deleteModerationRule(ruleId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/audience/moderation/rules/${ruleId}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete rule");
}

export async function getPolls(includeClosed = false): Promise<Poll[]> {
  const res = await fetch(`${API_BASE}/audience/polls?include_closed=${includeClosed}`);
  if (!res.ok) throw new Error("Failed to fetch polls");
  return res.json();
}

export async function createPoll(question: string, options: string[], durationSeconds = 60): Promise<Poll> {
  const res = await fetch(`${API_BASE}/audience/polls`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, options, duration_seconds: durationSeconds }),
  });
  if (!res.ok) throw new Error("Failed to create poll");
  return res.json();
}

export async function votePoll(pollId: string, optionIndex: number, userId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/audience/polls/${pollId}/vote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ option_index: optionIndex, user_id: userId }),
  });
  if (!res.ok) throw new Error("Failed to vote");
}

export async function closePoll(pollId: string): Promise<Poll> {
  const res = await fetch(`${API_BASE}/audience/polls/${pollId}/close`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to close poll");
  return res.json();
}

export async function getAudienceStats(): Promise<AudienceStats> {
  const res = await fetch(`${API_BASE}/audience/stats`);
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}

export async function startSimulation(rate = 0.33): Promise<void> {
  const res = await fetch(`${API_BASE}/audience/simulation/start?rate=${rate}`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to start simulation");
}

export async function stopSimulation(): Promise<void> {
  const res = await fetch(`${API_BASE}/audience/simulation/stop`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to stop simulation");
}
