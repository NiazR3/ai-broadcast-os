import { useState, useEffect, useRef } from "react";
import {
  getChat, flagMessage, moderateMessage,
  getModerationRules, createModerationRule, deleteModerationRule,
  startSimulation, stopSimulation,
} from "../lib/api";
import type { ChatMessage, ModerationRule } from "../lib/api";

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [rules, setRules] = useState<ModerationRule[]>([]);
  const [showFlagged, setShowFlagged] = useState(false);
  const [newRulePattern, setNewRulePattern] = useState("");
  const [newRuleAction, setNewRuleAction] = useState("flag");
  const [simRunning, setSimRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const pollInterval = useRef<number | null>(null);

  const fetchData = async () => {
    try {
      const msgs = await getChat(50, showFlagged);
      setMessages(msgs);
      setRules(await getModerationRules());
    } catch { /* ignore polling errors */ }
  };

  useEffect(() => {
    fetchData();
    pollInterval.current = window.setInterval(fetchData, 2000);
    return () => { if (pollInterval.current) clearInterval(pollInterval.current); };
  }, [showFlagged]);

  const handleFlag = async (id: string) => {
    try { await flagMessage(id); setError(null); fetchData(); }
    catch { setError("Failed to flag message"); }
  };

  const handleModerate = async (id: string, action: string) => {
    try { await moderateMessage(id, action); setError(null); fetchData(); }
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
      case "broadcaster": return "text-red-500";
      case "moderator": return "text-green-500";
      case "vip": return "text-purple-500";
      default: return "text-gray-700";
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="font-semibold">Live Chat</h3>
        <div className="flex gap-2">
          <button
            onClick={handleToggleSim}
            className={`px-3 py-1 text-xs rounded ${simRunning ? "bg-red-100 text-red-700 hover:bg-red-200" : "bg-green-100 text-green-700 hover:bg-green-200"}`}
          >
            {simRunning ? "Stop Sim" : "Start Sim"}
          </button>
          <button
            onClick={() => setShowFlagged(!showFlagged)}
            className={`px-3 py-1 text-xs rounded ${showFlagged ? "bg-orange-100 text-orange-700" : "bg-gray-100 text-gray-700"}`}
          >
            {showFlagged ? "All Messages" : "Flagged"}
          </button>
        </div>
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}

      {/* Chat feed */}
      <div ref={scrollRef} className="h-64 overflow-y-auto border rounded bg-gray-50 p-2 space-y-1">
        {messages.length === 0 ? (
          <p className="text-xs text-gray-400 text-center pt-8">
            {showFlagged ? "No flagged messages" : "No messages yet. Start the simulation."}
          </p>
        ) : (
          messages.map(m => (
            <div key={m.id} className={`text-sm p-1.5 rounded ${m.moderated ? "bg-orange-50 border border-orange-200" : "hover:bg-gray-100"}`}>
              <div className="flex justify-between items-start">
                <div className="flex-1 min-w-0">
                  <span className={`font-medium text-xs ${roleColor(m.user.role)}`}>
                    {m.user.display_name}
                  </span>
                  <span className="text-[10px] text-gray-400 ml-1">[{m.platform}]</span>
                  <p className="text-gray-800 break-words">{m.text}</p>
                  {m.moderated && (
                    <span className="text-[10px] text-orange-600">
                      Moderated: {m.moderation_action}
                    </span>
                  )}
                </div>
                {!m.moderated && (
                  <button onClick={() => handleFlag(m.id)}
                    className="text-[10px] text-red-500 hover:text-red-700 ml-2 flex-shrink-0">
                    Flag
                  </button>
                )}
                {m.moderated && m.moderation_action === "flag" && (
                  <div className="flex gap-1 ml-2 flex-shrink-0">
                    <button onClick={() => handleModerate(m.id, "approve")}
                      className="text-[10px] text-green-600 hover:text-green-800">Approve</button>
                    <button onClick={() => handleModerate(m.id, "timeout")}
                      className="text-[10px] text-orange-600 hover:text-orange-800">Timeout</button>
                    <button onClick={() => handleModerate(m.id, "ban")}
                      className="text-[10px] text-red-600 hover:text-red-800">Ban</button>
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Moderation rules */}
      <div>
        <h4 className="text-sm font-medium mb-1">Moderation Rules</h4>
        <div className="flex gap-2 mb-2">
          <input type="text" value={newRulePattern} placeholder="Regex pattern..."
            onChange={e => setNewRulePattern(e.target.value)}
            className="flex-1 px-2 py-1 border rounded text-xs" />
          <select value={newRuleAction} onChange={e => setNewRuleAction(e.target.value)}
            className="px-2 py-1 border rounded text-xs">
            <option value="flag">Flag</option>
            <option value="timeout">Timeout</option>
            <option value="ban">Ban</option>
          </select>
          <button onClick={handleAddRule}
            className="px-2 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700">
            Add
          </button>
        </div>
        <div className="space-y-1 max-h-24 overflow-y-auto">
          {rules.map(r => (
            <div key={r.id} className="flex justify-between items-center text-xs px-2 py-1 bg-gray-50 rounded">
              <span><code className="bg-gray-200 px-1 rounded">{r.pattern}</code> → {r.action}</span>
              <button onClick={() => handleDeleteRule(r.id)}
                className="text-red-500 hover:text-red-700">×</button>
            </div>
          ))}
          {rules.length === 0 && <p className="text-[10px] text-gray-400">No rules. Add a regex pattern above.</p>}
        </div>
      </div>
    </div>
  );
}
