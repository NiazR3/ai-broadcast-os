import { useState, useEffect } from "react";
import { getStatus, startBroadcast, stopBroadcast } from "../lib/api";
import type { BroadcastStatus as BroadcastStatusType } from "../lib/api";
import { PlatformCard } from "./PlatformCard";

export function BroadcastStatus() {
  const [status, setStatus] = useState<BroadcastStatusType | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const s = await getStatus();
      setStatus(s);
      setError(null);
    } catch (err) {
      setError("Failed to connect to broadcast service");
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleToggle = async () => {
    if (!status) return;
    setLoading(true);
    try {
      if (status.active) {
        const s = await stopBroadcast();
        setStatus(s);
      } else {
        const s = await startBroadcast();
        setStatus(s);
      }
    } catch {
      setError("Failed to toggle broadcast");
    }
    setLoading(false);
  };

  const formatUptime = (seconds: number): string => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  if (!status && error) {
    return (
      <div className="p-6 bg-red-50 rounded-lg border border-red-200">
        <p className="text-red-700">{error}</p>
        <button onClick={fetchStatus} className="mt-2 text-sm text-red-600 underline">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Broadcast Control</h2>
          {status && (
            <p className="text-sm text-gray-500">
              {status.active
                ? `Live for ${formatUptime(status.uptime_seconds)}`
                : "Offline"}
            </p>
          )}
        </div>
        <button
          onClick={handleToggle}
          disabled={loading}
          className={`px-6 py-3 rounded-lg font-semibold text-white transition-colors ${
            status?.active
              ? "bg-red-600 hover:bg-red-700"
              : "bg-green-600 hover:bg-green-700"
          } disabled:opacity-50`}
        >
          {loading ? "..." : status?.active ? "Stop" : "Go Live"}
        </button>
      </div>

      {/* Platform cards */}
      {status && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(status.platforms).map(([name, ps]) => (
            <PlatformCard key={name} name={name} status={ps} />
          ))}
        </div>
      )}
    </div>
  );
}
