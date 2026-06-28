import type { PlatformStatus as PlatformStatusType } from "../lib/api";

interface Props {
  name: string;
  status: PlatformStatusType;
}

const colorMap: Record<string, { border: string; bg: string }> = {
  twitch: { border: "border-purple-200", bg: "bg-purple-50" },
  youtube: { border: "border-red-200", bg: "bg-red-50" },
  facebook: { border: "border-blue-200", bg: "bg-blue-50" },
};

export function PlatformCard({ name, status }: Props) {
  const colors = colorMap[name] ?? { border: "border-gray-200", bg: "bg-gray-50" };

  return (
    <div className={`border rounded-lg p-4 ${colors.border} ${colors.bg}`}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold capitalize">{name}</h3>
        <span
          className={`w-3 h-3 rounded-full ${
            status.streaming ? "bg-green-500" : "bg-gray-400"
          }`}
        />
      </div>
      {status.error ? (
        <p className="text-sm text-red-600">{status.error}</p>
      ) : (
        <p className="text-sm text-gray-600 truncate" title={status.rtmp_url}>
          {status.streaming ? "Streaming" : "Configured"}
        </p>
      )}
    </div>
  );
}
