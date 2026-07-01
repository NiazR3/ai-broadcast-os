import type { PlatformStatus as PlatformStatusType } from "../lib/api";

interface Props {
  name: string;
  status: PlatformStatusType;
}

const platformConfig: Record<string, { label: string; dotColor: string; borderColor: string }> = {
  twitch: { label: "Twitch", borderColor: "border-l-brand", dotColor: "bg-brand" },
  youtube: { label: "YouTube", borderColor: "border-l-danger", dotColor: "bg-danger" },
  facebook: { label: "Facebook", borderColor: "border-l-info", dotColor: "bg-info" },
};

export function PlatformCard({ name, status }: Props) {
  const config = platformConfig[name] ?? {
    label: name,
    borderColor: "border-l-border",
    dotColor: "bg-text-muted",
  };

  // Simulated health metric — in production this comes from the API
  const streamHealth = status.streaming ? "good" : "inactive";
  const healthColor = streamHealth === "good" ? "text-live" : "text-text-muted";
  const healthLabel = streamHealth === "good" ? "Good" : "Inactive";

  return (
    <div className={`card border-l-4 ${config.borderColor} animate-fade-in`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-text capitalize">{config.label}</h3>
        <span
          className={`w-2.5 h-2.5 rounded-full ${
            status.streaming ? "live-dot" : "live-dot--off"
          }`}
          aria-label={status.streaming ? "Live" : "Offline"}
        />
      </div>

      {status.error ? (
        <div className="flex items-start gap-2" role="alert">
          <span className="text-danger text-xs leading-none mt-0.5 font-bold" aria-hidden="true">!</span>
          <p className="text-xs text-danger font-medium">{status.error}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {/* Status line */}
          <div className="flex items-center gap-2">
            <span className={`inline-block w-1.5 h-1.5 rounded-full ${config.dotColor}`} role="presentation" />
            <span className="text-xs text-text-secondary">
              {status.streaming ? "Live" : "Configured"}
            </span>
          </div>

          {/* Stream health indicator */}
          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center gap-1 text-xs font-medium ${healthColor}`}>
              <span className={`inline-block w-1.5 h-1.5 rounded-full ${
                streamHealth === "good" ? "bg-live" : "bg-text-muted"
              }`} />
              {healthLabel}
            </span>
          </div>

          {/* Bitrate / quality placeholder — expand when API provides real data */}
          {status.streaming && (
            <p className="text-xs text-text-muted font-mono">
              Stream active
            </p>
          )}
        </div>
      )}
    </div>
  );
}
