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
  const pollInterval = useRef<number | null>(null);

  const fetchPolls = async () => {
    try {
      const all = await getPolls(true);
      setPolls(all);
      const active = all.find(p => p.status === "active");
      setActivePoll(active || null);
      if (!active) setVoted(false);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    fetchPolls();
    pollInterval.current = window.setInterval(fetchPolls, 3000);
    return () => { if (pollInterval.current) clearInterval(pollInterval.current); };
  }, []);

  const handleCreate = async () => {
    if (!question.trim() || options.filter(o => o.trim()).length < 2) {
      setError("Question and at least 2 options required");
      return;
    }
    setError(null);
    try {
      await createPoll(question.trim(), options.filter(o => o.trim()), duration);
      setQuestion("");
      setOptions(["", ""]);
      await fetchPolls();
    } catch { setError("Failed to create poll"); }
  };

  const handleVote = async (optionIndex: number) => {
    if (!activePoll || voted) return;
    setError(null);
    try {
      await votePoll(activePoll.id, optionIndex, `user_${Date.now()}`);
      setVoted(true);
      await fetchPolls();
    } catch { setError("Failed to vote"); }
  };

  const handleClose = async () => {
    if (!activePoll) return;
    setError(null);
    try {
      await closePoll(activePoll.id);
      await fetchPolls();
    } catch { setError("Failed to close poll"); }
  };

  const totalVotes = (poll: Poll) => poll.options.reduce((s, o) => s + o.votes, 0);

  return (
    <div className="space-y-4">
      <h3 className="font-semibold">Polls</h3>

      {error && <p className="text-xs text-red-600">{error}</p>}

      {/* Active poll */}
      {activePoll ? (
        <div className="border rounded p-4 bg-blue-50">
          <div className="flex justify-between items-start mb-3">
            <div>
              <p className="font-medium text-sm">{activePoll.question}</p>
              <p className="text-xs text-gray-500">{totalVotes(activePoll)} total votes</p>
            </div>
            <button onClick={handleClose}
              className="px-2 py-1 text-xs border rounded hover:bg-blue-100">
              Close
            </button>
          </div>
          <div className="space-y-2">
            {activePoll.options.map((opt, i) => {
              const pct = totalVotes(activePoll) > 0
                ? Math.round((opt.votes / totalVotes(activePoll)) * 100)
                : 0;
              return (
                <div key={i}>
                  <button
                    onClick={() => handleVote(i)}
                    disabled={voted}
                    className="w-full text-left text-sm px-3 py-2 rounded border bg-white hover:bg-blue-50 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
                  >
                    <div className="flex justify-between mb-1">
                      <span>{opt.text}</span>
                      <span className="text-xs text-gray-500">{opt.votes} ({pct}%)</span>
                    </div>
                    <div className="h-2 bg-gray-200 rounded overflow-hidden">
                      <div className="h-full bg-blue-500 rounded transition-all duration-300"
                        style={{ width: `${pct}%` }} />
                    </div>
                  </button>
                </div>
              );
            })}
          </div>
          {voted && <p className="text-xs text-green-600 mt-2">Vote recorded!</p>}
        </div>
      ) : (
        <div className="border rounded p-4 bg-gray-50 text-center">
          <p className="text-sm text-gray-500">No active poll</p>
          <p className="text-xs text-gray-400">Create one below</p>
        </div>
      )}

      {/* Create poll form */}
      <div className="border rounded p-3 space-y-2">
        <h4 className="text-sm font-medium">Create Poll</h4>
        <input type="text" value={question} placeholder="Poll question..."
          onChange={e => setQuestion(e.target.value)}
          className="w-full px-3 py-2 border rounded text-sm" />
        {options.map((opt, i) => (
          <div key={i} className="flex gap-2">
            <input type="text" value={opt} placeholder={`Option ${i + 1}`}
              onChange={e => {
                const next = [...options];
                next[i] = e.target.value;
                setOptions(next);
              }}
              className="flex-1 px-2 py-1.5 border rounded text-sm" />
            {options.length > 2 && (
              <button onClick={() => setOptions(options.filter((_, j) => j !== i))}
                className="text-red-500 text-sm">&times;</button>
            )}
          </div>
        ))}
        <div className="flex gap-2">
          <button onClick={() => setOptions([...options, ""])}
            className="px-2 py-1 text-xs border rounded hover:bg-gray-50">
            + Add Option
          </button>
          <div className="flex items-center gap-1 ml-auto">
            <span className="text-xs text-gray-500">Duration:</span>
            <input type="number" value={duration} onChange={e => setDuration(Number(e.target.value))}
              className="w-16 px-2 py-1 border rounded text-xs" min={10} max={600} />
            <span className="text-xs text-gray-500">s</span>
          </div>
        </div>
        <button onClick={handleCreate}
          className="w-full px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">
          Create Poll
        </button>
      </div>

      {/* Poll history */}
      {polls.filter(p => p.status === "closed").length > 0 && (
        <div>
          <h4 className="text-sm font-medium mb-1">History</h4>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {polls.filter(p => p.status === "closed").slice(-5).reverse().map(p => (
              <div key={p.id} className="text-xs px-2 py-1 bg-gray-50 rounded flex justify-between">
                <span className="font-medium">{p.question}</span>
                <span className="text-gray-500">
                  {totalVotes(p)} votes · {p.options.reduce((best, o) => Math.max(best, o.votes), 0)} max
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
