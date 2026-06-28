import { BroadcastStatus } from "./components/BroadcastStatus";
import { SceneSwitcher } from "./components/SceneSwitcher";
import { ConfigPanel } from "./components/ConfigPanel";
import { AgentPanel } from "./components/AgentPanel";
import { Teleprompter } from "./components/Teleprompter";
import { PersonaPanel } from "./components/PersonaPanel";
import { ChatPanel } from "./components/ChatPanel";
import { PollPanel } from "./components/PollPanel";
import { useWebSocket } from "./hooks/useWebSocket";

function App() {
  const { lastEvent } = useWebSocket();

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-6 py-4">
        <h1 className="text-xl font-bold">AI Broadcast OS</h1>
      </header>

      <main className="max-w-5xl mx-auto p-6 space-y-8">
        {/* Live event indicator */}
        {lastEvent && (
          <div className="text-xs text-gray-500 text-right">
            Last event: {lastEvent.type}
            {lastEvent.scene && ` → ${lastEvent.scene}`}
          </div>
        )}

        {/* Broadcast status + controls */}
        <BroadcastStatus />

        {/* Teleprompter */}
        <section className="bg-white rounded-lg shadow-sm p-6">
          <Teleprompter />
        </section>

        {/* Director + Agent controls */}
        <section className="bg-white rounded-lg shadow-sm p-6">
          <AgentPanel />
        </section>

        {/* Persona profiles */}
        <section className="bg-white rounded-lg shadow-sm p-6">
          <PersonaPanel />
        </section>

        {/* Scene switcher */}
        <section className="bg-white rounded-lg shadow-sm p-6">
          <SceneSwitcher />
        </section>

        {/* Config */}
        <section className="bg-white rounded-lg shadow-sm p-6">
          <ConfigPanel />
        </section>

        {/* Audience chat */}
        <section className="bg-white rounded-lg shadow-sm p-6">
          <ChatPanel />
        </section>

        {/* Audience polls */}
        <section className="bg-white rounded-lg shadow-sm p-6">
          <PollPanel />
        </section>
      </main>
    </div>
  );
}

export default App;
