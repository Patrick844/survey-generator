import { useState } from "react";
import type { Session } from "./types";
import Landing from "./components/Landing";
import ChatView from "./components/ChatView";

function getSurveyId(): string | null {
  return new URLSearchParams(window.location.search).get("survey_id");
}

export default function App() {
  const surveyId = getSurveyId();
  const [session, setSession] = useState<Session | null>(null);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-2xl px-4 py-3 flex items-center gap-2">
          <span className="text-xl">💬</span>
          <span className="font-semibold text-slate-800">Employee Survey</span>
        </div>
      </header>

      <main className="flex-1 mx-auto w-full max-w-2xl px-4 py-6">
        {!session ? (
          <Landing surveyId={surveyId} onStarted={setSession} />
        ) : (
          <ChatView
            session={session}
            onSession={setSession}
            onReset={() => setSession(null)}
          />
        )}
      </main>
    </div>
  );
}
