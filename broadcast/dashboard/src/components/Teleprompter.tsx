import { useState, useEffect, useRef } from "react";
import { getDirectorStatus, generateDialogue, directorNext } from "../lib/api";
import type { DirectorStatus } from "../lib/api";

export function Teleprompter() {
  const [director, setDirector] = useState<DirectorStatus | null>(null);
  const [hostText, setHostText] = useState("");
  const [cohostText, setCohostText] = useState("");
  const [segmentTitle, setSegmentTitle] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const d = await getDirectorStatus();
        setDirector(d);
      } catch { /* ignore */ }
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleNext = async () => {
    try {
      const result = await directorNext();
      setSegmentTitle(result.segment.title);
      // Auto-generate dialogue
      const d = await generateDialogue();
      setHostText(d.host.lines.map(l => l.text).join("\n\n"));
      setCohostText(d.cohost.lines.map(l => l.text).join("\n\n"));
      if (autoScroll && scrollRef.current) {
        scrollRef.current.scrollTop = 0;
      }
    } catch { /* ignore */ }
  };

  return (
    <div className="bg-gray-900 text-white rounded-lg p-6 min-h-[300px] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-bold">Teleprompter</h3>
          {director && (
            <p className="text-xs text-gray-400">
              {director.script_title || "No script"} · {segmentTitle || "No segment"}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleNext}
            className="px-4 py-1.5 bg-blue-600 rounded text-sm hover:bg-blue-700"
          >
            Next Segment
          </button>
          <label className="flex items-center gap-1 text-xs text-gray-400">
            <input type="checkbox" checked={autoScroll} onChange={e => setAutoScroll(e.target.checked)} />
            Auto
          </label>
        </div>
      </div>

      {/* Teleprompter Text */}
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto max-h-[400px]">
        {!hostText && !cohostText ? (
          <div className="flex items-center justify-center h-32 text-gray-500 text-sm">
            Advance to a segment and generate dialogue
          </div>
        ) : (
          <>
            {hostText && (
              <div className="border-l-4 border-blue-500 pl-4 py-2">
                <p className="text-xs font-semibold text-blue-400 mb-1">Host</p>
                <p className="text-lg leading-relaxed">{hostText}</p>
              </div>
            )}
            {cohostText && (
              <div className="border-l-4 border-purple-500 pl-4 py-2">
                <p className="text-xs font-semibold text-purple-400 mb-1">Co-Host</p>
                <p className="text-lg leading-relaxed">{cohostText}</p>
              </div>
            )}
          </>
        )}
      </div>

      {/* Controls */}
      <div className="flex gap-3 mt-4 pt-3 border-t border-gray-700">
        <button
          onClick={async () => {
            try {
              const d = await generateDialogue();
              setHostText(d.host.lines.map(l => l.text).join("\n\n"));
              setCohostText(d.cohost.lines.map(l => l.text).join("\n\n"));
            } catch { /* ignore */ }
          }}
          className="text-xs px-3 py-1 bg-gray-700 rounded hover:bg-gray-600"
        >
          Regenerate
        </button>
      </div>
    </div>
  );
}
