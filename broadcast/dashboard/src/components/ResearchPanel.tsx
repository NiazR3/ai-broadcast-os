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
  const [listLoading, setListLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [results, setResults] = useState<ResearchResult[]>([]);
  const [selected, setSelected] = useState<ResearchResult | null>(null);
  const [extractedTopics, setExtractedTopics] = useState<string[]>([]);
  const [autoResearch, setAutoResearch] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchResults = useCallback(async () => {
    try {
      const data = await listResearchResults();
      setResults(data);
    } catch {
      setError("Failed to load research history");
    }
    setListLoading(false);
  }, []);

  useEffect(() => {
    fetchResults();
  }, [fetchResults]);

  const handleResearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await submitResearch(query.trim());
      setQuery("");
      setExtractedTopics([]);
      await fetchResults();
    } catch {
      setError("Research request failed");
    } finally {
      setLoading(false);
    }
  };

  const handleExtract = async () => {
    if (!query.trim()) return;
    setError(null);
    try {
      const { topics } = await extractTopics(query.trim());
      setExtractedTopics(topics);
    } catch {
      setError("Topic extraction failed");
    }
  };

  const handleTagClick = (topic: string) => {
    setQuery(topic);
  };

  const handleSelectResult = async (r: ResearchResult) => {
    setSelected(r);
    setDetailLoading(true);
    setError(null);
    // Simulate brief load for detail transition
    await new Promise((resolve) => setTimeout(resolve, 150));
    setDetailLoading(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleResearch();
    }
  };

  return (
    <div className="bg-surface border border-border rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-text uppercase tracking-[0.08em]">Research</h2>
        <label className="flex items-center gap-2 text-xs text-text-secondary cursor-pointer select-none">
          <input
            type="checkbox"
            checked={autoResearch}
            onChange={(e) => setAutoResearch(e.target.checked)}
            className="rounded border-border bg-base text-brand focus:ring-brand/50 focus:ring-2"
          />
          Auto-research
        </label>
      </div>

      {/* Error banner */}
      {error && (
        <div className="bg-danger-bg border border-danger/30 rounded-lg px-4 py-3 mb-4" role="alert">
          <p className="text-sm text-danger">{error}</p>
        </div>
      )}

      {/* Search input */}
      <div className="flex gap-2 mb-4" role="search">
        <div className="flex-1">
          <label htmlFor="research-query" className="sr-only">Research topic</label>
          <input
            id="research-query"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter a topic to research..."
            className="w-full px-3.5 py-2.5 bg-base border border-border rounded-lg text-sm text-text placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/50 transition-all"
          />
        </div>
        <button
          onClick={handleResearch}
          disabled={loading || !query.trim()}
          className="px-4 py-2.5 bg-brand hover:bg-brand-hover text-white rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Researching
            </span>
          ) : (
            "Research"
          )}
        </button>
        <button
          onClick={handleExtract}
          disabled={!query.trim()}
          className="px-3.5 py-2.5 bg-hover hover:bg-elevated border border-border text-text-secondary hover:text-text rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          Extract
        </button>
      </div>

      {/* Extracted topics pills */}
      {extractedTopics.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-4">
          {extractedTopics.map((topic, i) => (
            <button
              key={i}
              onClick={() => handleTagClick(topic)}
              className="bg-brand-muted/30 text-brand hover:bg-brand-muted/50 text-xs px-2.5 py-1 rounded-full border border-brand/20 hover:border-brand/40 focus:outline-none focus:ring-2 focus:ring-brand/50 transition-all"
            >
              {topic}
            </button>
          ))}
          <button
            onClick={() => setExtractedTopics([])}
            className="text-xs text-text-muted hover:text-text-secondary ml-1 transition-colors focus:outline-none focus:ring-2 focus:ring-brand/50 rounded px-1"
          >
            Clear
          </button>
        </div>
      )}

      {/* Split pane */}
      <div className="flex gap-5">
        {/* Results list sidebar */}
        <div className="w-64 shrink-0">
          <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2.5">
            History ({results.length})
          </h3>
          {listLoading ? (
            <div className="space-y-2 animate-pulse" aria-hidden="true">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-16 bg-elevated rounded-lg" />
              ))}
            </div>
          ) : (
            <div className="space-y-1.5 max-h-96 overflow-y-auto pr-1 scrollbar-thin">
              {results.map((r) => (
                <button
                  key={r.id}
                  onClick={() => handleSelectResult(r)}
                  className={`w-full text-left p-3 rounded-lg text-sm transition-all border ${
                    selected?.id === r.id
                      ? "bg-hover border-brand/40 text-text"
                      : "bg-elevated border-transparent text-text-secondary hover:bg-hover hover:border-border"
                  } focus:outline-none focus:ring-2 focus:ring-brand/50`}
                >
                  <p className="font-medium truncate text-sm leading-snug">
                    {r.key_points[0]?.slice(0, 50) || "Untitled research"}
                  </p>
                  <p className="text-xs text-text-muted mt-1.5 font-mono">
                    {r.sources.length} source{r.sources.length !== 1 ? "s" : ""} &middot;{" "}
                    {r.fact_checks.length} fact check{r.fact_checks.length !== 1 ? "s" : ""}
                  </p>
                </button>
              ))}
              {results.length === 0 && (
                <p className="text-xs text-text-muted italic px-1">No results yet</p>
              )}
            </div>
          )}
        </div>

        {/* Selected result detail */}
        <div className="flex-1 min-w-0" aria-live="polite">
          {detailLoading ? (
            <div className="animate-pulse space-y-4" aria-hidden="true">
              <div className="h-4 bg-elevated rounded w-3/4" />
              <div className="h-3 bg-elevated rounded w-full" />
              <div className="h-3 bg-elevated rounded w-5/6" />
              <div className="h-3 bg-elevated rounded w-4/5" />
              <div className="h-4 bg-elevated rounded w-1/3 mt-6" />
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="h-10 bg-elevated rounded" />
                ))}
              </div>
            </div>
          ) : selected ? (
            <div className="space-y-5">
              <p className="text-sm text-text leading-relaxed">{selected.summary}</p>

              {selected.key_points.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2.5">
                    Key Points
                  </h4>
                  <ul className="space-y-1.5">
                    {selected.key_points.map((pt, i) => (
                      <li
                        key={i}
                        className="text-sm text-text leading-relaxed pl-4 border-l-2 border-brand/30"
                      >
                        {pt}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {selected.sources.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2.5">
                    Sources
                  </h4>
                  <div className="space-y-2">
                    {selected.sources.map((s, i) => (
                      <div
                        key={i}
                        className="text-sm bg-elevated border border-border rounded-lg p-3"
                      >
                        <a
                          href={s.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-brand hover:text-brand-hover font-medium transition-colors"
                        >
                          {s.title}
                        </a>
                        <p className="text-text-muted text-xs mt-1">{s.snippet}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selected.fact_checks.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2.5">
                    Fact Checks
                  </h4>
                  <div className="space-y-2.5">
                    {selected.fact_checks.map((fc, i) => (
                      <div
                        key={i}
                        className="bg-elevated border border-border rounded-lg p-4 text-sm"
                      >
                        <p className="font-medium text-text mb-2">{fc.claim}</p>
                        <span
                          className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            fc.verdict === "supported"
                              ? "bg-live/15 text-live border border-live/30"
                              : fc.verdict === "contradicted"
                              ? "bg-danger-bg text-danger border border-danger/30"
                              : "bg-warning/15 text-warning border border-warning/30"
                          }`}
                        >
                          {fc.verdict}
                        </span>
                        <p className="mt-2 text-text-secondary text-xs leading-relaxed">
                          {fc.explanation}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 border border-dashed border-border rounded-lg">
              <div className="text-center">
                <p className="text-sm text-text-muted">Select a result from the history</p>
                <p className="text-xs text-text-muted/60 mt-1">to view its full details</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
