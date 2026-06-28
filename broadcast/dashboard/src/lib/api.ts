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
