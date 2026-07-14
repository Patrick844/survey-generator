import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { Session } from "../types";
import Message from "./Message";
import AnswerWidget from "./AnswerWidget";
import Completion from "./Completion";

interface Props {
  session: Session;
  onSession: (s: Session) => void;
  onReset: () => void;
}

function Dots() {
  return (
    <div className="flex gap-1 items-center">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}

export default function ChatView({ session, onSession, onReset }: Props) {
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [text, setText] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [session.chat_history.length, pending]);

  const submit = async (message: string) => {
    if (!message.trim() || pending) return;
    setPending(message);
    setError("");
    setText("");
    try {
      onSession(await api.sendMessage(session.session_id, message));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Please try again.");
    } finally {
      setPending(null);
    }
  };

  const reset = async () => {
    try {
      await api.deleteSession(session.session_id);
    } catch {
      /* ignore */
    }
    onReset();
  };

  const q = session.current_question;
  const pct = session.total_questions ? (session.progress / session.total_questions) * 100 : 0;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
          <div className="h-full bg-blue-500 transition-all" style={{ width: `${pct}%` }} />
        </div>
        <p className="text-xs text-slate-500 mt-1">
          {session.progress}/{session.total_questions} answered
        </p>
      </div>

      <div className="space-y-3">
        {session.chat_history.map((m, i) => (
          <Message key={i} role={m.role} content={m.content} />
        ))}
        {pending && <Message role="user" content={pending} />}
        {pending && (
          <div className="flex justify-start">
            <div className="bg-white border border-slate-200 rounded-2xl px-4 py-3">
              <Dots />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {session.completed ? (
        <Completion onReset={reset} />
      ) : !pending && q ? (
        <>
          <AnswerWidget key={q.id} question={q} disabled={false} onSubmit={submit} />
          <form
            onSubmit={(e) => {
              e.preventDefault();
              submit(text);
            }}
            className="flex gap-2"
          >
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="…or type your answer"
              className="flex-1 border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
            <button
              type="submit"
              disabled={!text.trim()}
              className="bg-slate-700 text-white font-medium rounded-lg px-4 hover:bg-slate-800 disabled:opacity-40 transition-colors"
            >
              Send
            </button>
          </form>
        </>
      ) : null}

      {!session.completed && (
        <button onClick={reset} className="text-xs text-slate-400 hover:text-slate-600 self-start">
          Reset survey
        </button>
      )}
    </div>
  );
}
