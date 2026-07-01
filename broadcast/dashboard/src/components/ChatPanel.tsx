import { useState, useEffect, useRef } from "react";
import {
  getChat, flagMessage, moderateMessage,
  getModerationRules, createModerationRule, deleteModerationRule,
  startSimulation, stopSimulation,
} from "../lib/api";
import type { ChatMessage, ModerationRule } from "../lib/api";

type ConfirmAction = {
  type: "timeout" | "ban";
  messageId: string;
  userName: string;
} | null;

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [rules, setRules] = useState<ModerationRule[]>([]);
  const [showFlagged, setShowFlagged] = useState(false);
  const [newRulePattern, setNewRulePattern] = useState("");
  const [newRuleAction, setNewRuleAction] = useState("flag");
  const [simRunning, setSimRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const pollInterval = useRef<number | null>(null);
  const prevMessageCount = useRef(0);
  const autoScrollRef = useRef(true);

  const fetchData = async () => {
    try {
      const msgs = await getChat(50, showFlagged);
      // Check if we should auto-scroll (user hasn't scrolled up manually)
      const container = scrollRef.current;
      if (container) {
        const isAtBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 50;
        autoScrollRef.current = isAtBottom;
      }
      setMessages(msgs);
      setRules(await getModerationRules());
    } catch { /* ignore polling errors */ }
  };

  useEffect(() => {
    fetchData();
    pollInterval.current = window.setInterval(fetchData, 2000);
    return () => { if (pollInterval.current) clearInterval(pollInterval.current); };
  }, [showFlagged]);

  // Auto-scroll to bottom when new messages arrive (if user is at bottom)
  useEffect(() => {
    if (autoScrollRef.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
    prevMessageCount.current = messages.length;
  }, [messages.length]);

  const handleFlag = async (id: string) => {
    try { await flagMessage(id); setError(null); fetchData(); }
    catch { setError("Failed to flag message"); }
  };

  const handleModerate = async (id: string, action: string) => {
    try { await moderateMessage(id, action); setError(null); setConfirmAction(null); fetchData(); }
    catch { setError("Failed to moderate"); }
  };

  const handleAddRule = async () => {
    if (!newRulePattern.trim()) return;
    try {
      await createModerationRule(newRulePattern.trim(), newRuleAction);
      setNewRulePattern("");
      setError(null);
      fetchData();
    } catch { setError("Failed to add rule"); }
  };

  const handleDeleteRule = async (id: string) => {
    try { await deleteModerationRule(id); setError(null); fetchData(); }
    catch { setError("Failed to delete rule"); }
  };

  const handleToggleSim = async () => {
    try {
      if (simRunning) { await stopSimulation(); setSimRunning(false); }
      else { await startSimulation(0.5); setSimRunning(true); }
      setError(null);
    } catch { setError("Failed to toggle simulation"); }
  };

  const roleColor = (role: string) => {
    switch (role) {
      case "broadcaster": return "text-red-400";
      case "moderator": return "text-live";
      case "vip": return "text-purple-400";
      default: return "text-text-secondary";
    }
  };

  const platformBadge = (platform: string): string => {
    const p = platform.toLowerCase();
    if (p === "twitch") return "badge--info";
    if (p === "youtube") return "badge--danger";
    if (p === "facebook") return "badge--accent";
    return "badge--default";
  };

  return (
    <div className="space-y-5">
      {/* ── Section Header ── */}
      <div className="section-header">
        <div>
          <h3 className="section-header__title">Live Chat</h3>
          <p className="section-header__subtitle">
            Real-time audience feed
            {messages.length > 0 && (
              <span className="ml-1.5 text-text-muted">
                &middot; <span className="data-value">{messages.length}</span> shown
              </span>
            )}
          </p>
        </div>
        <div className="section-header__actions">
          <button
            onClick={handleToggleSim}
            className={`btn btn--sm ${simRunning ? "btn-ghost text-warning hover:bg-warning/10" : "btn-primary"}`}
          >
            <span className={`inline-block h-1.5 w-1.5 rounded-full ${
              simRunning ? "bg-warning animate-pulse" : "bg-live"
            }`} />
            {simRunning ? "Stop Sim" : "Start Sim"}
          </button>
          <button
            onClick={() => setShowFlagged(!showFlagged)}
            className={`btn btn--sm ${showFlagged ? "btn-ghost text-accent" : "btn-ghost"}`}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" />
              <line x1="4" y1="22" x2="4" y2="15" />
            </svg>
            {showFlagged ? "All Messages" : "Flagged"}
          </button>
        </div>
      </div>

      {/* ── Error Banner ── */}
      {error && (
        <div className="animate-fade-in-down flex items-center gap-2.5 rounded-lg border border-danger/30 bg-danger-bg px-4 py-3 text-sm text-danger" role="alert">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0" aria-hidden="true">
            <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          {error}
        </div>
      )}

      {/* ── Confirmation Dialog for Destructive Moderation ── */}
      {confirmAction && (
        <div className="bg-accent-bg border border-warning/40 rounded-lg p-4 animate-fade-in-down" role="alertdialog" aria-label="Confirm moderation action">
          <div className="flex items-start gap-3">
            <span className="text-warning text-sm leading-none mt-0.5 font-bold" aria-hidden="true">!</span>
            <div className="flex-1">
              <p className="text-warning font-semibold text-sm">
                {confirmAction.type === "ban" ? "Ban" : "Timeout"} user?
              </p>
              <p className="text-text-secondary text-xs mt-1">
                {confirmAction.type === "ban"
                  ? `Permanently ban "${confirmAction.userName}" from chat? This cannot be undone.`
                  : `Temporarily timeout "${confirmAction.userName}"?`}
              </p>
              <div className="flex items-center gap-2 mt-3">
                <button
                  onClick={() => handleModerate(confirmAction.messageId, confirmAction.type)}
                  className={`btn btn--sm ${confirmAction.type === "ban" ? "btn-danger" : "btn-ghost text-warning border-warning/40 hover:bg-warning/10"}`}
                >
                  {confirmAction.type === "ban" ? "Yes, Ban" : "Yes, Timeout"}
                </button>
                <button
                  onClick={() => setConfirmAction(null)}
                  className="btn btn-ghost btn--sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Chat Feed ── */}
      <div className="card p-0 overflow-hidden">
        <div
          ref={scrollRef}
          className="h-96 overflow-y-auto bg-bg-base p-3 space-y-0.5"
          aria-live="polite"
          aria-label="Chat messages"
        >
          {messages.length === 0 ? (
            <p className="pt-10 text-center text-xs text-text-muted">
              {showFlagged ? "No flagged messages" : "No messages yet. Start the simulation."}
            </p>
          ) : (
            messages.map(m => (
              <div
                key={m.id}
                className={`rounded-lg px-3 py-2 text-sm transition-colors ${
                  m.moderated
                    ? "border border-warning/20 bg-warning/5"
                    : "hover:bg-bg-hover"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    {/* User info row */}
                    <div className="flex items-center gap-1.5">
                      <span className={`data-value text-xs font-semibold ${roleColor(m.user.role)}`}>
                        {m.user.display_name}
                      </span>
                      <span className={`badge ${platformBadge(m.platform)}`}>
                        {m.platform}
                      </span>
                      {m.moderated && (
                        <span className="badge badge--warning">
                          {m.moderation_action}
                        </span>
                      )}
                    </div>
                    {/* Message text */}
                    <p className="mt-0.5 break-words text-text-secondary leading-relaxed">
                      {m.text}
                    </p>
                  </div>

                  {/* Moderation actions */}
                  <div className="shrink-0">
                    {!m.moderated && (
                      <button
                        onClick={() => handleFlag(m.id)}
                        className="btn btn-ghost btn--sm text-danger/70 hover:text-danger"
                        aria-label="Flag message"
                      >
                        Flag
                      </button>
                    )}
                    {m.moderated && m.moderation_action === "flag" && (
                      <div className="flex gap-1">
                        <button
                          onClick={() => handleModerate(m.id, "approve")}
                          className="btn btn-ghost btn--sm text-live hover:bg-live/10"
                          aria-label="Approve message"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => setConfirmAction({
                            type: "timeout",
                            messageId: m.id,
                            userName: m.user.display_name,
                          })}
                          className="btn btn-ghost btn--sm text-warning hover:bg-warning/10"
                          aria-label="Timeout user"
                        >
                          Timeout
                        </button>
                        <button
                          onClick={() => setConfirmAction({
                            type: "ban",
                            messageId: m.id,
                            userName: m.user.display_name,
                          })}
                          className="btn btn-ghost btn--sm text-danger hover:bg-danger-bg"
                          aria-label="Ban user"
                        >
                          Ban
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* ── Moderation Rules ── */}
      <div className="card">
        <h4 className="mb-3 text-sm font-semibold text-text">Moderation Rules</h4>

        {/* Add rule row */}
        <div className="flex gap-2 mb-3">
          <div className="flex-1">
            <label htmlFor="rule-pattern-input" className="sr-only">Rule pattern</label>
            <input
              id="rule-pattern-input"
              type="text"
              value={newRulePattern}
              placeholder="Regex pattern..."
              onChange={e => setNewRulePattern(e.target.value)}
              className="input-field"
              onKeyDown={e => { if (e.key === "Enter") handleAddRule(); }}
            />
          </div>
          <div>
            <label htmlFor="rule-action-select" className="sr-only">Rule action</label>
            <select
              id="rule-action-select"
              value={newRuleAction}
              onChange={e => setNewRuleAction(e.target.value)}
              className="input-field w-28 shrink-0"
            >
              <option value="flag">Flag</option>
              <option value="timeout">Timeout</option>
              <option value="ban">Ban</option>
            </select>
          </div>
          <button onClick={handleAddRule} className="btn btn-primary">
            Add
          </button>
        </div>

        {/* Rule list */}
        <div className="max-h-24 space-y-1 overflow-y-auto">
          {rules.length === 0 ? (
            <p className="py-4 text-center text-xs text-text-muted">
              No rules. Add a regex pattern above.
            </p>
          ) : (
            rules.map(r => (
              <div
                key={r.id}
                className="flex items-center justify-between rounded-lg bg-bg-elevated px-3 py-2 text-xs"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <code className="shrink-0 rounded bg-bg-hover px-1.5 py-0.5 font-mono text-xs text-text-secondary">
                    {r.pattern}
                  </code>
                  <span className="inline-flex items-center gap-1 text-text-muted">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                      <line x1="5" y1="12" x2="19" y2="12" />
                    </svg>
                    {r.action}
                  </span>
                </div>
                <button
                  onClick={() => handleDeleteRule(r.id)}
                  className="ml-2 flex h-5 w-5 shrink-0 items-center justify-center rounded text-text-muted transition-colors hover:bg-danger-bg hover:text-danger"
                  aria-label={`Delete rule ${r.pattern}`}
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
