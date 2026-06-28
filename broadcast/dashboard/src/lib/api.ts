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

export async function duplicatePersona(id: string): Promise<PersonaProfile> {
  const original = await getPersona(id);
  const { id: _unused, ...data } = original;
  data.name = `${data.name} (Copy)`;
  return createPersona(data);
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

// ── Research API types ─────────────────────────────────────────────
export interface ResearchResult {
  id: string;
  topic_id: string;
  summary: string;
  key_points: string[];
  sources: { url: string; title: string; snippet: string; relevance_score: number }[];
  fact_checks: { claim: string; verdict: string; explanation: string }[];
  created_at: number;
}

export interface TopicExtract {
  topics: string[];
  text: string;
}

// ── Research API functions ─────────────────────────────────────────
export async function submitResearch(query: string, segmentId = "", segmentTitle = ""): Promise<ResearchResult> {
  const res = await fetch(`${API_BASE}/research/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, segment_id: segmentId, segment_title: segmentTitle }),
  });
  if (!res.ok) throw new Error("Failed to submit research");
  return res.json();
}

export async function listResearchResults(): Promise<ResearchResult[]> {
  const res = await fetch(`${API_BASE}/research/results`);
  if (!res.ok) throw new Error("Failed to list research results");
  return res.json();
}

export async function getResearchResult(id: string): Promise<ResearchResult> {
  const res = await fetch(`${API_BASE}/research/results/${id}`);
  if (!res.ok) throw new Error("Failed to get research result");
  return res.json();
}

export async function extractTopics(text: string): Promise<TopicExtract> {
  const res = await fetch(`${API_BASE}/research/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error("Failed to extract topics");
  return res.json();
}

// ── Media API types ────────────────────────────────────────────────
export type ChartType = "bar" | "line" | "pie";
export type AssetType = "chart" | "text_overlay";

export interface ChartConfig {
  chart_type: ChartType;
  title: string;
  labels: string[];
  datasets: { label: string; values: number[] }[];
  width?: number;
  height?: number;
  colors?: string[];
}

export interface TextOverlayConfig {
  text: string;
  font_size?: number;
  color?: string;
  background_color?: string;
  width?: number;
  height?: number;
}

export interface MediaAsset {
  id: string;
  type: AssetType;
  segment_id: string;
  svg_content: string;
  metadata: Record<string, unknown>;
  status: "generated" | "assigned" | "deleted";
  created_at: number;
}

// ── Media API functions ────────────────────────────────────────────
export async function createChart(config: ChartConfig): Promise<MediaAsset> {
  const res = await fetch(`${API_BASE}/media/chart`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error("Failed to create chart");
  return res.json();
}

export async function createTextOverlay(config: TextOverlayConfig): Promise<MediaAsset> {
  const res = await fetch(`${API_BASE}/media/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error("Failed to create text overlay");
  return res.json();
}

export async function listAssets(segmentId?: string, type?: AssetType): Promise<MediaAsset[]> {
  const params = new URLSearchParams();
  if (segmentId) params.set("segment_id", segmentId);
  if (type) params.set("type", type);
  const query = params.toString() ? `?${params}` : "";
  const res = await fetch(`${API_BASE}/media/assets${query}`);
  if (!res.ok) throw new Error("Failed to list assets");
  return res.json();
}

export async function getAsset(id: string): Promise<MediaAsset> {
  const res = await fetch(`${API_BASE}/media/assets/${id}`);
  if (!res.ok) throw new Error("Failed to get asset");
  return res.json();
}

export async function deleteAsset(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/media/assets/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete asset");
}

export async function assignAsset(assetId: string, segmentId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/media/assets/${assetId}/assign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ segment_id: segmentId }),
  });
  if (!res.ok) throw new Error("Failed to assign asset");
}

// ── Analytics API types ─────────────────────────────────────────────
export interface BroadcastSession {
  id: string;
  started_at: number;
  ended_at: number | null;
  duration_seconds: number;
  peak_viewers: number;
  avg_viewers: number;
  total_chat_messages: number;
  unique_chatters: number;
  platforms: string[];
  status: "live" | "ended";
}

export interface AnalyticsReport {
  session_id: string;
  summary: {
    duration_seconds: number;
    peak_viewers: number;
    avg_viewers: number;
    platforms: string[];
    status: string;
  };
  engagement: {
    total_chat_messages: number;
    unique_chatters: number;
    messages_per_minute: number;
    top_chatters: Array<{ user: string; count: number }>;
    polls_conducted: number;
    assets_created: number;
  };
  timeline: Array<{
    id: string;
    session_id: string;
    timestamp: number;
    event_type: string;
    payload: Record<string, unknown>;
  }>;
  generated_at: number;
}

export interface DashboardData {
  live_session: BroadcastSession | null;
  recent_sessions: BroadcastSession[];
  totals: {
    total_sessions: number;
    total_messages: number;
    total_duration_hours: number;
    all_time_peak: number;
  };
}

export interface LiveMetrics {
  live: boolean;
  session: BroadcastSession | null;
}

// ── Analytics API functions ─────────────────────────────────────────
export async function listSessions(limit = 20, status?: string): Promise<BroadcastSession[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set("status", status);
  const res = await fetch(`${API_BASE}/analytics/sessions?${params}`);
  if (!res.ok) throw new Error(`Failed to list sessions: ${res.status}`);
  return res.json();
}

export async function getSession(id: string): Promise<BroadcastSession> {
  const res = await fetch(`${API_BASE}/analytics/sessions/${id}`);
  if (!res.ok) throw new Error(`Failed to get session: ${res.status}`);
  return res.json();
}

export async function getSessionReport(id: string): Promise<AnalyticsReport> {
  const res = await fetch(`${API_BASE}/analytics/sessions/${id}/report`);
  if (!res.ok) throw new Error(`Failed to get report: ${res.status}`);
  return res.json();
}

export async function getSessionReportCsv(id: string): Promise<string> {
  const res = await fetch(`${API_BASE}/analytics/sessions/${id}/report.csv`);
  if (!res.ok) throw new Error(`Failed to get CSV: ${res.status}`);
  return res.text();
}

export async function getLiveMetrics(): Promise<LiveMetrics> {
  const res = await fetch(`${API_BASE}/analytics/live`);
  if (!res.ok) throw new Error(`Failed to get live metrics: ${res.status}`);
  return res.json();
}

export async function getDashboardData(): Promise<DashboardData> {
  const res = await fetch(`${API_BASE}/analytics/dashboard`);
  if (!res.ok) throw new Error(`Failed to get dashboard data: ${res.status}`);
  return res.json();
}
