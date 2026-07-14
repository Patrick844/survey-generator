import { useState } from "react";
import type { Question, BackendQuestion, QuestionType } from "../types/models";

// Backend base URL. Baked in at build time from the VITE_API_BASE env var
// (see Dockerfile build arg); falls back to localhost for local dev.
const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

function toBackendQuestion(q: Question): BackendQuestion {
  const qt: QuestionType = q.type;
  const meta = q.metadata ?? {};
  const opts = q.options ?? [];

  let options: string[] = [];
  let prompt = q.question;

  if (qt === "distribution") {
    // Named categories — assign a percentage to each (no letter codes).
    options = opts.map((o) => o.label || o.code);
    if (opts.length > 0) {
      const lines = opts.map((o) => `- ${o.label || o.code}`).join("\n");
      prompt = `${q.question}\n\n${lines}`;
    }
  } else if (qt === "single_selection" || qt === "multiple_selection") {
    const label = (o: { code: string; label: string }) =>
      /^[A-Z]$/.test(o.code) ? `${o.code}. ${o.label}` : o.label;
    options = opts.map(label);
    if (opts.length > 0) {
      const lines = opts.map(label).join("\n");
      const maxNote =
        qt === "multiple_selection"
          ? meta.max_choices
            ? ` Pick up to ${meta.max_choices}.`
            : " Pick all that apply."
          : "";
      prompt = `${q.question}${maxNote}\n\n${lines}`;
    }
  }

  return {
    id: q.id,
    category: q.category,
    question_type: qt,
    prompt,
    options,
    min_value: meta.min_value ?? null,
    max_value: meta.max_value ?? null,
    max_choices: meta.max_choices ?? null,
    min_length: meta.min_length ?? 2,
  };
}

interface GenerateChatbotModalProps {
  questions: Question[];
  onClose: () => void;
}

export default function GenerateChatbotModal({ questions, onClose }: GenerateChatbotModalProps) {
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [surveyUrl, setSurveyUrl] = useState("");
  const [surveyId, setSurveyId] = useState("");
  const [copied, setCopied] = useState(false);

  const payload = { questions: questions.map(toBackendQuestion) };

  const deploy = async () => {
    setStatus("loading");
    try {
      const res = await fetch(`${API_BASE}/surveys`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data = await res.json() as { survey_url: string; survey_id: string };
      setSurveyUrl(data.survey_url);
      setSurveyId(data.survey_id);
      setStatus("success");
    } catch {
      setStatus("error");
    }
  };

  const copyLink = async () => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(surveyUrl);
      } else {
        // navigator.clipboard is unavailable over plain HTTP (non-secure
        // context), so fall back to a temporary textarea + execCommand.
        const textarea = document.createElement("textarea");
        textarea.value = surveyUrl;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-green-100 flex items-center justify-center">
              <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
              </svg>
            </div>
            <h2 className="text-base font-bold text-gray-900">Generate Chatbot Survey</h2>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors cursor-pointer">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
          {status === "success" ? (
            <div className="flex flex-col items-center gap-5 py-6">
              <div className="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center">
                <svg className="w-7 h-7 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="text-center">
                <h3 className="text-lg font-bold text-gray-900 mb-1">Survey Created!</h3>
                <p className="text-sm text-gray-500">{questions.length} questions deployed — share the link below with employees.</p>
              </div>

              {/* Survey link */}
              <div className="w-full bg-green-50 border border-green-200 rounded-xl p-4 space-y-3">
                <p className="text-xs font-semibold text-green-700 uppercase tracking-wide">Employee Survey Link</p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-xs bg-white border border-green-200 rounded-lg px-3 py-2 text-gray-700 break-all">
                    {surveyUrl}
                  </code>
                  <button onClick={copyLink}
                    className="shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-lg bg-green-600 text-white text-xs font-semibold hover:bg-green-700 transition-colors cursor-pointer">
                    {copied ? (
                      <>
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                        Copied
                      </>
                    ) : (
                      <>
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                        Copy
                      </>
                    )}
                  </button>
                </div>
                <p className="text-xs text-green-600">Survey ID: <span className="font-mono">{surveyId}</span></p>
              </div>

              <button onClick={onClose}
                className="px-6 py-2.5 rounded-xl border border-gray-200 text-sm font-semibold text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer">
                Close
              </button>
            </div>
          ) : (
            <>
              <p className="text-sm text-gray-500">
                This will publish your survey of <strong>{questions.length} question{questions.length === 1 ? "" : "s"}</strong> and
                generate a shareable link you can send to employees.
              </p>

              <div className="bg-gray-50 border border-gray-100 rounded-xl divide-y divide-gray-100">
                {questions.map((q, i) => (
                  <div key={q.id} className="flex items-start gap-3 px-4 py-3">
                    <span className="shrink-0 w-6 h-6 rounded-full bg-blue-100 text-blue-600 text-xs font-bold flex items-center justify-center">{i + 1}</span>
                    <div className="min-w-0">
                      <p className="text-sm text-gray-700 truncate">{q.question || <span className="italic text-gray-400">Untitled question</span>}</p>
                      <p className="text-xs text-gray-400">{q.category} · {q.type.replace(/_/g, " ")}</p>
                    </div>
                  </div>
                ))}
              </div>

              {status === "error" && (
                <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
                  <p className="font-semibold mb-1">Could not reach the chatbot backend</p>
                  <p className="text-xs text-red-500">Please try again in a moment.</p>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        {status !== "success" && (
          <div className="px-6 py-4 border-t border-gray-100 flex gap-3">
            <button onClick={onClose}
              className="flex-1 py-2.5 rounded-xl border border-gray-200 text-sm font-semibold text-gray-500 hover:bg-gray-50 transition-colors cursor-pointer">
              Cancel
            </button>
            <button onClick={deploy} disabled={status === "loading"}
              className="flex-1 py-2.5 rounded-xl bg-green-600 text-white text-sm font-semibold hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer flex items-center justify-center gap-2">
              {status === "loading" ? (
                <>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 00-8 8h4z" />
                  </svg>
                  Creating survey…
                </>
              ) : "Create & Get Link"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
