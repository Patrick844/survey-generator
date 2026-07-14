import { useState } from "react";
import type { ReactNode } from "react";
import type { PublicQuestion } from "../types";

interface Sub {
  q: PublicQuestion;
  disabled: boolean;
  onSubmit: (message: string) => void;
}

const optionBtn =
  "px-4 py-2.5 rounded-xl border-2 border-slate-200 bg-white text-slate-700 text-sm font-medium hover:border-blue-400 hover:bg-blue-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-left";
const optionBtnOn =
  "px-4 py-2.5 rounded-xl border-2 border-blue-500 bg-blue-50 text-blue-700 text-sm font-semibold hover:bg-blue-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-left";
const submitBtn =
  "bg-blue-600 text-white font-semibold rounded-lg px-5 py-2 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors";

function Shell({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-4">
      <p className="text-sm font-semibold text-slate-700 mb-3">{label}</p>
      {children}
    </div>
  );
}

function clampInt(v: string, lo: number, hi: number): number {
  const n = Math.round(Number(v));
  if (Number.isNaN(n)) return lo;
  return Math.min(hi, Math.max(lo, n));
}

function SingleSelect({ q, disabled, onSubmit }: Sub) {
  return (
    <Shell label="Choose one:">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {q.options.map((opt) => (
          <button key={opt} disabled={disabled} onClick={() => onSubmit(opt)} className={optionBtn}>
            {opt}
          </button>
        ))}
      </div>
    </Shell>
  );
}

function MultiSelect({ q, disabled, onSubmit }: Sub) {
  const [selected, setSelected] = useState<string[]>([]);
  const max = q.max_choices;
  const atLimit = max != null && selected.length >= max;
  const toggle = (opt: string) =>
    setSelected((s) => (s.includes(opt) ? s.filter((x) => x !== opt) : atLimit ? s : [...s, opt]));

  return (
    <Shell label={max ? `Choose up to ${max}:` : "Choose all that apply:"}>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {q.options.map((opt) => {
          const on = selected.includes(opt);
          return (
            <button
              key={opt}
              disabled={disabled || (atLimit && !on)}
              onClick={() => toggle(opt)}
              className={on ? optionBtnOn : optionBtn}
            >
              {on ? `✓ ${opt}` : opt}
            </button>
          );
        })}
      </div>
      {atLimit && <p className="text-xs text-slate-500 mt-2">Maximum of {max} reached — deselect one to change.</p>}
      <div className="mt-3">
        <button disabled={disabled || selected.length === 0} onClick={() => onSubmit(selected.join(", "))} className={submitBtn}>
          Submit answer
        </button>
      </div>
    </Shell>
  );
}

function Rating({ q, disabled, onSubmit }: Sub) {
  const lo = Math.round(q.min_value ?? 1);
  const hi = Math.max(lo, Math.round(q.max_value ?? 5));
  const range = Array.from({ length: hi - lo + 1 }, (_, i) => lo + i);
  return (
    <Shell label={`Rate from ${lo} to ${hi}:`}>
      <div className="flex flex-wrap gap-2">
        {range.map((v) => (
          <button key={v} disabled={disabled} onClick={() => onSubmit(String(v))} className={`${optionBtn} w-12 text-center`}>
            {v}
          </button>
        ))}
      </div>
    </Shell>
  );
}

function Distribution({ q, disabled, onSubmit }: Sub) {
  const [vals, setVals] = useState<Record<string, number>>(() =>
    Object.fromEntries(q.options.map((o) => [o, 0]))
  );
  const total = Object.values(vals).reduce((a, b) => a + b, 0);
  return (
    <Shell label="Assign a percentage to each — the total must equal 100%:">
      <div className="space-y-2">
        {q.options.map((opt) => (
          <div key={opt} className="flex items-center gap-3">
            <span className="flex-1 text-sm text-slate-700">{opt}</span>
            <input
              type="number"
              min={0}
              max={100}
              step={5}
              value={vals[opt]}
              disabled={disabled}
              onChange={(e) => setVals((s) => ({ ...s, [opt]: clampInt(e.target.value, 0, 100) }))}
              className="w-20 border border-slate-300 rounded-lg px-2 py-1 text-right focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
            <span className="text-slate-400 text-sm w-3">%</span>
          </div>
        ))}
      </div>
      <p className={`text-sm mt-3 ${total === 100 ? "text-green-600" : "text-slate-500"}`}>
        Total: {total}%{total === 100 ? " ✓" : " — adjust so it adds up to 100%"}
      </p>
      <div className="mt-3">
        <button
          disabled={disabled || total !== 100}
          onClick={() => onSubmit(q.options.filter((o) => vals[o] > 0).map((o) => `${vals[o]}% ${o}`).join(", "))}
          className={submitBtn}
        >
          Submit answer
        </button>
      </div>
    </Shell>
  );
}

function NumberInput({ q, disabled, onSubmit }: Sub) {
  const [val, setVal] = useState("");
  const { min_value: min, max_value: max } = q;
  const num = val === "" ? null : Number(val);
  const inRange =
    num !== null && !Number.isNaN(num) && (min == null || num >= min) && (max == null || num <= max);
  return (
    <Shell label={min != null && max != null ? `Enter a number between ${min} and ${max}:` : "Enter your answer:"}>
      <input
        type="number"
        value={val}
        disabled={disabled}
        placeholder="Type a number"
        onChange={(e) => setVal(e.target.value)}
        className="w-full border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
      />
      {val !== "" && !inRange && min != null && max != null && (
        <p className="text-sm text-amber-600 mt-1">Must be between {min} and {max}.</p>
      )}
      <div className="mt-3">
        <button disabled={disabled || !inRange} onClick={() => onSubmit(String(num))} className={submitBtn}>
          Submit answer
        </button>
      </div>
    </Shell>
  );
}

function PercentInput({ disabled, onSubmit }: Omit<Sub, "q">) {
  const [val, setVal] = useState("");
  const num = val === "" ? null : Number(val);
  const ok = num !== null && !Number.isNaN(num) && num >= 0 && num <= 100;
  return (
    <Shell label="Enter a percentage (0–100):">
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={val}
          disabled={disabled}
          placeholder="0–100"
          onChange={(e) => setVal(e.target.value)}
          className="w-32 border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <span className="text-slate-400">%</span>
      </div>
      {val !== "" && !ok && <p className="text-sm text-amber-600 mt-1">Must be between 0 and 100.</p>}
      <div className="mt-3">
        <button disabled={disabled || !ok} onClick={() => onSubmit(`${num}%`)} className={submitBtn}>
          Submit answer
        </button>
      </div>
    </Shell>
  );
}

function FreeText({ q, disabled, onSubmit }: Sub) {
  const [val, setVal] = useState("");
  const min = q.min_length ?? 0;
  const trimmed = val.trim();
  const ok = trimmed.length >= min;
  return (
    <Shell label={min > 0 ? `Your answer (minimum ${min} characters):` : "Your answer:"}>
      <textarea
        value={val}
        disabled={disabled}
        rows={3}
        placeholder="Type your answer here…"
        onChange={(e) => setVal(e.target.value)}
        className="w-full border border-slate-300 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-blue-400"
      />
      {trimmed !== "" && !ok && (
        <p className="text-sm text-amber-600 mt-1">
          {trimmed.length}/{min} characters — a little more.
        </p>
      )}
      <div className="mt-3">
        <button disabled={disabled || !ok} onClick={() => onSubmit(trimmed)} className={submitBtn}>
          Submit answer
        </button>
      </div>
    </Shell>
  );
}

export default function AnswerWidget({ question, disabled, onSubmit }: {
  question: PublicQuestion;
  disabled: boolean;
  onSubmit: (message: string) => void;
}) {
  const shared = { q: question, disabled, onSubmit };
  switch (question.question_type) {
    case "single_selection":
      return question.options.length ? <SingleSelect {...shared} /> : null;
    case "multiple_selection":
      return question.options.length ? <MultiSelect {...shared} /> : null;
    case "rating":
      return <Rating {...shared} />;
    case "distribution":
      return question.options.length ? <Distribution {...shared} /> : null;
    case "number":
      return <NumberInput {...shared} />;
    case "percentage":
      return <PercentInput disabled={disabled} onSubmit={onSubmit} />;
    case "free_text":
      return <FreeText {...shared} />;
    default:
      return null;
  }
}
