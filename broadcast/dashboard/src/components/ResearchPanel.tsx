import { useState, useEffect, useCallback } from "react";
import {
  submitResearch,
  listResearchResults,
  extractTopics,
} from "../lib/api";
import type { ResearchResult } from "../lib/api";

export function ResearchPanel() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<ResearchResult[]>([]);
  const [selected, setSelected] = useState<ResearchResult | null>(null);
  const [autoResearch, setAutoResearch] = useState(true);

  const fetchResults = useCallback(async () => {
    try {
      const data = await listResearchResults();
      setResults(data);
    } catch {
      // silently fail
    }
  }, []);

  useEffect(() => {
    fetchResults();
  }, [fetchResults]);

  const handleResearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      await submitResearch(query.trim());
      setQuery("");
      await fetchResults();
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  const handleExtract = async () => {
    if (!query.trim()) return;
    try {
      const { topics } = await extractTopics(query.trim());
      setQuery(`Topics: ${topics.join(", ") || "none"}`);
    } catch {
      // silently fail
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleResearch();
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Research</h2>
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={autoResearch}
            onChange={(e) => setAutoResearch(e.target.checked)}
            className="rounded"
          />
          Auto-research
        </label>
      </div>

      {/* Search input */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter a topic to research..."
          className="flex-1 border rounded px-3 py-2 text-sm"
        />
        <button
          onClick={handleResearch}
          disabled={loading || !query.trim()}
          className="bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Researching..." : "Research"}
        </button>
        <button
          onClick={handleExtract}
          disabled={!query.trim()}
          className="bg-gray-200 text-gray-700 px-3 py-2 rounded text-sm hover:bg-gray-300 disabled:opacity-50"
        >
          Extract
        </button>
      </div>

      <div className="flex gap-4">
        {/* Results list */}
        <div className="w-1/3 border-r pr-4">
          <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">
            History ({results.length})
          </h3>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {results.map((r) => (
              <button
                key={r.id}
                onClick={() => setSelected(r)}
                className={`w-full text-left p-2 rounded text-sm transition-colors ${
                  selected?.id === r.id
                    ? "bg-blue-50 border border-blue-200"
                    : "hover:bg-gray-50 border border-transparent"
                }`}
              >
                <div className="font-medium truncate">
                  {r.key_points[0]?.slice(0, 50) || "Research result"}
                </div>
                <div className="text-xs text-gray-400 mt-1">
                  {r.sources.length} source{r.sources.length !== 1 ? "s" : ""} ·{" "}
                  {r.fact_checks.length} fact check{r.fact_checks.length !== 1 ? "s" : ""}
                </div>
              </button>
            ))}
            {results.length === 0 && (
              <p className="text-xs text-gray-400 italic">No results yet</p>
            )}
          </div>
        </div>

        {/* Selected result detail */}
        <div className="flex-1">
          {selected ? (
            <div className="space-y-4">
              <p className="text-sm text-gray-700 leading-relaxed">{selected.summary}</p>

              {selected.key_points.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Key Points</h4>
                  <ul className="list-disc list-inside space-y-1">
                    {selected.key_points.map((pt, i) => (
                      <li key={i} className="text-sm text-gray-700">{pt}</li>
                    ))}
                  </ul>
                </div>
              )}

              {selected.sources.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Sources</h4>
                  <div className="space-y-2">
                    {selected.sources.map((s, i) => (
                      <div key={i} className="text-sm">
                        <a
                          href={s.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:underline font-medium"
                        >
                          {s.title}
                        </a>
                        <p className="text-gray-500 text-xs">{s.snippet}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selected.fact_checks.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Fact Checks</h4>
                  <div className="space-y-2">
                    {selected.fact_checks.map((fc, i) => (
                      <div key={i} className="border rounded p-3 text-sm">
                        <p className="font-medium">{fc.claim}</p>
                        <span
                          className={`inline-block mt-1 px-2 py-0.5 rounded text-xs font-medium ${
                            fc.verdict === "supported"
                              ? "bg-green-100 text-green-800"
                              : fc.verdict === "contradicted"
                              ? "bg-red-100 text-red-800"
                              : "bg-yellow-100 text-yellow-800"
                          }`}
                        >
                          {fc.verdict}
                        </span>
                        <p className="mt-1 text-gray-500">{fc.explanation}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-400 italic">
              Select a result from the history to view details
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
