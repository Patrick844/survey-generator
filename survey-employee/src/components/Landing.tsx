import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api, ApiError } from "../api";
import type { Session, Survey } from "../types";

interface Props {
  surveyId: string | null;
  onStarted: (session: Session) => void;
}

function Card({ children }: { children: ReactNode }) {
  return <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">{children}</div>;
}

export default function Landing({ surveyId, onStarted }: Props) {
  const [survey, setSurvey] = useState<Survey | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [name, setName] = useState("");
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!surveyId) return;
    api.getSurvey(surveyId).then(setSurvey).catch(() => setNotFound(true));
  }, [surveyId]);

  if (!surveyId) {
    return <Card><p className="text-slate-600">Missing survey link — please use the link you were given.</p></Card>;
  }
  if (notFound) {
    return <Card><p className="text-amber-700">This survey link doesn't look valid. Please double-check the link you were given.</p></Card>;
  }

  const start = async () => {
    setStarting(true);
    setError("");
    try {
      onStarted(await api.startSession(surveyId, name));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Please try again.");
      setStarting(false);
    }
  };

  return (
    <Card>
      <h1 className="text-2xl font-bold text-slate-900 mb-1">{survey?.title ?? "Employee Survey"}</h1>
      {survey && (
        <p className="text-sm text-slate-500 mb-4">
          {survey.total_questions} short questions · a few minutes · answers saved automatically
        </p>
      )}
      <p className="text-slate-600 mb-6">
        You'll answer a few questions in a friendly chat — there are no wrong answers, just share your honest perspective.
      </p>

      <label className="block text-sm font-medium text-slate-700 mb-1">Your name (optional)</label>
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="You can stay anonymous"
        className="w-full border border-slate-300 rounded-lg px-3 py-2 mb-4 focus:outline-none focus:ring-2 focus:ring-blue-400"
      />

      {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

      <button
        onClick={start}
        disabled={starting}
        className="w-full bg-blue-600 text-white font-semibold rounded-lg py-2.5 hover:bg-blue-700 disabled:opacity-50 transition-colors"
      >
        {starting ? "Starting…" : "Start survey"}
      </button>
    </Card>
  );
}
