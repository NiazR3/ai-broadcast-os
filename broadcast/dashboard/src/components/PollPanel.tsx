import { useState, useEffect, useRef } from "react";
import { getPolls, createPoll, votePoll, closePoll } from "../lib/api";
import type { Poll } from "../lib/api";

export function PollPanel() {
  const [polls, setPolls] = useState<Poll[]>([]);
  const [activePoll, setActivePoll] = useState<Poll | null>(null);
  const [question, setQuestion] = useState("");
  const [options, setOptions] = useState(["", ""]);
  const [duration, setDuration] = useState(60);
  const [voted, setVoted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const pollInterval = useRef<number | null>(null);

  const fetchPolls = async () => {
    try {
      const all = await getPolls(true);
      setPolls(all);
      const active = all.find((p) => p.status === "active");
      setActivePoll(active || null);
      if (!active) setVoted(false);
    } catch {
      /* ignore */
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchPolls();
    pollInterval.current = window.setInterval(fetchPolls, 3000);
    return () => {
      if (pollInterval.current) clearInterval(pollInterval.current);
    };
  }, []);

  const handleCreate = async () => {
    if (!question.trim() || options.filter((o) => o.trim()).length < 2) {
      setError("Question and at least 2 options required");
      return;
    }
    setError(null);
    try {
      await createPoll(question.trim(), options.filter((o) => o.trim()), duration);
      setQuestion("");
      setOptions(["", ""]);
      await fetchPolls();
    } catch {
      setError("Failed to create poll");
    }
  };

  const handleVote = async (optionIndex: number) => {
    if (!activePoll || voted) return;
    setError(null);
    try {
      await votePoll(activePoll.id, optionIndex, `user_${Date.now()}`);
      setVoted(true);
      await fetchPolls();
    } catch {
      setError("Failed to vote");
    }
  };

  const handleClose = async () => {
    if (!activePoll) return;
    setError(null);
    try {
      await closePoll(activePoll.id);
      await fetchPolls();
    } catch {
      setError("Failed to close poll");
    }
  };

  const totalVotes = (poll: Poll) => poll.options.reduce((s, o) => s + o.votes, 0);

  return (
    <div className="bg-surface border border-border rounded-lg p-6 space-y-5">
      <h3 className="text-xs font-semibold text-text uppercase tracking-[0.08em]">Polls</h3>

      {/* Error banner */}
      {error && (
        <div className="bg-danger-bg border border-danger/30 rounded-lg px-4 py-3" role="alert">
          <p className="text-sm text-danger">{error}</p>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="animate-pulse space-y-4" aria-hidden="true">
          <div className="h-32 bg-elevated rounded-lg" />
          <div className="h-48 bg-elevated rounded-lg" />
        </div>
      )}

      {/* Active poll */}
      {!loading && activePoll ? (
        <div className="bg-elevated border border-accent/30 rounded-lg p-5" aria-live="polite">
          <div className="flex justify-between items-start mb-4">
            <div className="space-y-1">
              <p className="text-sm font-medium text-text leading-snug">{activePoll.question}</p>
              <p className="text-xs text-text-muted font-mono">{totalVotes(activePoll)} total votes</p>
            </div>
            <button
              onClick={handleClose}
              className="btn btn-ghost btn--sm"
            >
              Close
            </button>
          </div>
          <div className="space-y-2.5">
            {activePoll.options.map((opt, i) => {
              const pct =
                totalVotes(activePoll) > 0
                  ? Math.round((opt.votes / totalVotes(activePoll)) * 100)
                  : 0;
              return (
                <div key={i}>
                  <button
                    onClick={() => handleVote(i)}
                    disabled={voted}
                    className="w-full text-left text-sm px-4 py-3 rounded-lg border border-border bg-surface hover:bg-hover disabled:opacity-50 disabled:cursor-not-allowed transition-all focus:outline-none focus:ring-2 focus:ring-accent/50"
                  >
                    <div className="flex justify-between mb-1.5">
                      <span className="text-text">{opt.text}</span>
                      <span className="text-xs font-mono text-text-muted">
                        {opt.votes} ({pct}%)
                      </span>
                    </div>
                    <div className="h-2 bg-base rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent rounded-full transition-all duration-500 ease-out"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </button>
                </div>
              );
            })}
          </div>
          {voted && (
            <p className="text-xs text-live mt-3 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-live" />
              Vote recorded!
            </p>
          )}
        </div>
      ) : !loading ? (
        <div className="border border-border rounded-lg p-6 text-center bg-elevated/50">
          <p className="text-sm text-text-muted">No active poll</p>
          <p className="text-xs text-text-muted/60 mt-1.5">Create one below to engage your audience</p>
        </div>
      ) : null}

      {/* Create poll form */}
      <div className="bg-elevated border border-border rounded-lg p-5 space-y-3.5">
        <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Create Poll</h4>
        <div>
          <label htmlFor="poll-question" className="sr-only">Poll question</label>
          <input
            id="poll-question"
            type="text"
            value={question}
            placeholder="Poll question..."
            onChange={(e) => setQuestion(e.target.value)}
            className="input-field"
          />
        </div>
        <div className="space-y-2" role="group" aria-label="Poll options">
          {options.map((opt, i) => (
            <div key={i} className="flex gap-2">
              <label htmlFor={`poll-option-${i}`} className="sr-only">Option {i + 1}</label>
              <input
                id={`poll-option-${i}`}
                type="text"
                value={opt}
                placeholder={`Option ${i + 1}`}
                onChange={(e) => {
                  const next = [...options];
                  next[i] = e.target.value;
                  setOptions(next);
                }}
                className="input-field flex-1"
              />
              {options.length > 2 && (
                <button
                  onClick={() => setOptions(options.filter((_, j) => j !== i))}
                  className="btn btn-ghost btn--sm text-danger hover:bg-danger-bg"
                  aria-label={`Remove option ${i + 1}`}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              )}
            </div>
          ))}
        </div>
        <div className="flex items-center justify-between gap-3">
          <button
            onClick={() => setOptions([...options, ""])}
            className="btn btn-ghost btn--sm"
          >
            + Add Option
          </button>
          <div className="flex items-center gap-2">
            <label htmlFor="poll-duration" className="text-xs text-text-muted">Duration:</label>
            <input
              id="poll-duration"
              type="number"
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="input-field w-16 text-center"
              min={10}
              max={600}
            />
            <span className="text-xs text-text-muted font-mono">s</span>
          </div>
        </div>
        <button
          onClick={handleCreate}
          className="btn btn-primary w-full"
        >
          Create Poll
        </button>
      </div>

      {/* Poll history */}
      {!loading && polls.filter((p) => p.status === "closed").length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2.5">
            History
          </h4>
          <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1 scrollbar-thin">
            {polls
              .filter((p) => p.status === "closed")
              .slice(-5)
              .reverse()
              .map((p) => (
                <div
                  key={p.id}
                  className="text-xs px-3 py-2 bg-hover border border-border/50 rounded-lg flex justify-between items-center hover:bg-elevated transition-colors"
                >
                  <span className="font-medium text-text truncate mr-2">{p.question}</span>
                  <span className="text-text-muted font-mono whitespace-nowrap shrink-0">
                    {totalVotes(p)} votes &middot; {p.options.reduce((best, o) => Math.max(best, o.votes), 0)} max
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
