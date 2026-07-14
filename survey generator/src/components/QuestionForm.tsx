import type { Dispatch, SetStateAction } from "react";
import type { QuestionDraft, QuestionType, Option, Metadata } from "../types/models";

interface TypeDef {
  type: QuestionType;
  icon: string;
  label: string;
  desc: string;
}

const TYPES: TypeDef[] = [
  { type: "single_selection",   icon: "◉", label: "Single Selection",   desc: "One answer from a list" },
  { type: "multiple_selection",  icon: "☑", label: "Multiple Selection",  desc: "Multiple answers from a list" },
  { type: "distribution",        icon: "⊞", label: "Distribution",        desc: "Distribute a total across categories" },
  { type: "number",              icon: "#", label: "Number",              desc: "A numeric value" },
  { type: "rating",              icon: "★", label: "Rating",              desc: "A score within a range" },
  { type: "percentage",          icon: "%", label: "Percentage",          desc: "A value from 0 to 100" },
  { type: "free_text",           icon: "✎", label: "Free Text",           desc: "Open-ended written response" },
];

const HAS_OPTIONS: QuestionType[] = ["single_selection", "multiple_selection", "distribution"];

const NEXT_CODE = (opts: Option[]): string => {
  const used = new Set(opts.map((o) => o.code));
  for (let c = 65; c <= 90; c++) {
    const ch = String.fromCharCode(c);
    if (!used.has(ch)) return ch;
  }
  return String(opts.length + 1);
};

interface QuestionFormProps {
  form: QuestionDraft;
  setForm: Dispatch<SetStateAction<QuestionDraft>>;
  onSave: () => void;
  onClose: () => void;
  isEditing: boolean;
}

export default function QuestionForm({ form, setForm, onSave, onClose, isEditing }: QuestionFormProps) {
  const update = (key: keyof QuestionDraft, val: QuestionDraft[keyof QuestionDraft]) =>
    setForm((f) => ({ ...f, [key]: val }) as QuestionDraft);

  const updateMeta = (key: keyof Metadata, val: Metadata[keyof Metadata]) =>
    setForm((f) => ({ ...f, metadata: { ...f.metadata, [key]: val } }));

  const handleTypeChange = (type: QuestionType) => {
    const freshMeta: Metadata = {};
    if (type === "rating")             { freshMeta.min_value = 1; freshMeta.max_value = 5; }
    if (type === "free_text")          freshMeta.min_length = 2;
    // multiple_selection: leave max_choices unset → "pick all that apply".
    // The admin opts into a cap by entering a number.
    update("type", type);
    update("metadata", freshMeta);
    if (HAS_OPTIONS.includes(type) && form.options.length < 2) {
      update("options", [{ code: "A", label: "" }, { code: "B", label: "" }]);
    }
  };

  const addOption = () => {
    const code = NEXT_CODE(form.options);
    update("options", [...form.options, { code, label: "" }]);
  };

  const removeOption = (i: number) =>
    update("options", form.options.filter((_, idx) => idx !== i));

  const updateOption = (i: number, key: keyof Option, val: string) =>
    update("options", form.options.map((o, idx) => idx === i ? { ...o, [key]: val } as Option : o));

  const meta = form.metadata ?? {};

  const canSave =
    form.question.trim() &&
    form.category.trim() &&
    (!HAS_OPTIONS.includes(form.type) || form.options.length >= 2);

  return (
    <div className="fixed right-0 top-0 h-full w-full max-w-lg bg-white shadow-2xl z-50 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
        <h2 className="text-base font-bold text-gray-900">
          {isEditing ? "Edit Question" : "Add Question"}
        </h2>
        <button onClick={onClose} className="p-2 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors cursor-pointer">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">

        {/* Category */}
        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Category</label>
          <input
            value={form.category}
            onChange={(e) => update("category", e.target.value)}
            placeholder="e.g. Work-Life Balance"
            className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
          />
        </div>

        {/* Question text */}
        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Question</label>
          <textarea
            value={form.question}
            onChange={(e) => update("question", e.target.value)}
            rows={3}
            placeholder="Type your survey question here…"
            className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent resize-none"
          />
        </div>

        {/* Question type */}
        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Question Type</label>
          <div className="grid grid-cols-2 gap-2">
            {TYPES.map(({ type, icon, label, desc }) => (
              <button
                key={type}
                type="button"
                onClick={() => handleTypeChange(type)}
                className={`text-left px-3 py-2.5 rounded-xl border-2 transition-all cursor-pointer ${
                  form.type === type
                    ? "border-blue-500 bg-blue-50"
                    : "border-gray-100 hover:border-blue-200 hover:bg-blue-50/40"
                }`}
              >
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className="text-base leading-none">{icon}</span>
                  <span className={`text-xs font-semibold ${form.type === type ? "text-blue-700" : "text-gray-700"}`}>{label}</span>
                </div>
                <p className="text-xs text-gray-400 leading-snug">{desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Options */}
        {HAS_OPTIONS.includes(form.type) && (
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              {form.type === "distribution" ? "Categories" : "Options"} <span className="text-gray-300 font-normal">(min 2)</span>
            </label>
            <div className="space-y-2">
              {form.options.map((o, i) => (
                <div key={i} className="flex items-center gap-2">
                  {form.type !== "distribution" && (
                    <input
                      value={o.code}
                      onChange={(e) => updateOption(i, "code", e.target.value.toUpperCase())}
                      maxLength={4}
                      placeholder="A"
                      className="w-12 text-center text-sm font-bold text-blue-600 border border-gray-200 rounded-lg px-2 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
                    />
                  )}
                  <input
                    value={o.label}
                    onChange={(e) => updateOption(i, "label", e.target.value)}
                    placeholder={form.type === "distribution" ? `Category ${i + 1} name` : `Option ${i + 1} label`}
                    className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
                  />
                  <button
                    onClick={() => removeOption(i)}
                    disabled={form.options.length <= 2}
                    className="p-2 rounded-lg text-red-300 hover:text-red-500 hover:bg-red-50 disabled:opacity-20 transition-colors cursor-pointer">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
            <button onClick={addOption}
              className="mt-2 flex items-center gap-1.5 text-xs text-blue-500 hover:text-blue-700 font-medium cursor-pointer">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              Add option
            </button>
          </div>
        )}

        {/* Max choices (multiple_selection) */}
        {form.type === "multiple_selection" && (
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Max Choices</label>
            <input
              type="number"
              min={1}
              max={form.options.length || 10}
              value={meta.max_choices ?? ""}
              onChange={(e) => updateMeta("max_choices", parseInt(e.target.value) || null)}
              placeholder="No limit"
              className="w-28 text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
            <p className="text-xs text-gray-400 mt-1.5">Leave empty to let employees pick all that apply. Enter a number to cap selections.</p>
          </div>
        )}

        {/* Range (number / rating) */}
        {(form.type === "number" || form.type === "rating") && (
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Range</label>
            <div className="flex items-center gap-3">
              <div className="flex-1">
                <p className="text-xs text-gray-400 mb-1">Min</p>
                <input type="number"
                  value={meta.min_value ?? ""}
                  onChange={(e) => updateMeta("min_value", parseFloat(e.target.value))}
                  className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
                />
              </div>
              <span className="text-gray-300 mt-5">–</span>
              <div className="flex-1">
                <p className="text-xs text-gray-400 mb-1">Max</p>
                <input type="number"
                  value={meta.max_value ?? ""}
                  onChange={(e) => updateMeta("max_value", parseFloat(e.target.value))}
                  className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
                />
              </div>
            </div>
          </div>
        )}

        {/* Percentage info */}
        {form.type === "percentage" && (
          <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-xs text-green-700">
            <p className="font-semibold mb-1">Percentage</p>
            <p>The chatbot will expect a numeric response between 0 and 100. No additional configuration needed.</p>
          </div>
        )}

        {/* Min length (free_text) */}
        {form.type === "free_text" && (
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Min Answer Length <span className="text-gray-300 font-normal">(characters)</span></label>
            <input
              type="number"
              min={1}
              value={meta.min_length ?? ""}
              onChange={(e) => updateMeta("min_length", parseInt(e.target.value) || null)}
              className="w-28 text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-gray-100 flex gap-3">
        <button onClick={onClose}
          className="flex-1 py-2.5 rounded-xl border border-gray-200 text-sm font-semibold text-gray-500 hover:bg-gray-50 transition-colors cursor-pointer">
          Cancel
        </button>
        <button onClick={onSave} disabled={!canSave}
          className="flex-1 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer">
          {isEditing ? "Save Changes" : "Add Question"}
        </button>
      </div>
    </div>
  );
}
