import { useMemo, useState } from "react";
import type { QuestionDraft } from "../types/models";
import { QUESTION_BANK, bankItemToDraft, LIKERT_MIN, LIKERT_MAX } from "../data/questionBank";

interface QuestionLibraryProps {
  /** Statements already added to the survey — used to mark/disable duplicates. */
  usedStatements: string[];
  /** False when the survey has hit its question cap. */
  canAdd: boolean;
  count: number;
  max: number;
  onSelect: (draft: QuestionDraft) => void;
  onClose: () => void;
}

// The framework's single answer type today. Adding more later means pushing
// extra entries here and tagging items — the drill-down already supports it.
const RATING_TYPE = {
  id: "rating",
  label: `Rating (${LIKERT_MIN}–${LIKERT_MAX})`,
  scale: "1 = Strongly disagree → 5 = Strongly agree",
};

export default function QuestionLibrary({ usedStatements, canAdd, count, max, onSelect, onClose }: QuestionLibraryProps) {
  // Drill-down: category -> answer type -> questions.
  const [category, setCategory] = useState<string | null>(null);
  const [typeId, setTypeId] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const used = useMemo(
    () => new Set(usedStatements.map((s) => s.trim().toLowerCase())),
    [usedStatements],
  );

  const activeCat = QUESTION_BANK.find((c) => c.name === category) ?? null;
  const step: 1 | 2 | 3 = !category ? 1 : !typeId ? 2 : 3;

  const query = search.trim().toLowerCase();
  const questions = useMemo(() => {
    const items = activeCat?.items ?? [];
    return query ? items.filter((i) => i.toLowerCase().includes(query)) : items;
  }, [activeCat, query]);

  const goCategories = () => { setCategory(null); setTypeId(null); setSearch(""); };
  const goTypes = () => { setTypeId(null); setSearch(""); };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl h-[85vh] flex flex-col overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <h2 className="text-base font-bold text-gray-900">Question Library</h2>
            <p className="text-xs text-gray-400">
              300-item Work Dynamics framework — 10 categories. Questions are added as-is.
            </p>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors cursor-pointer">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Breadcrumb */}
        <div className="px-6 py-2.5 border-b border-gray-100 flex items-center gap-1.5 text-xs">
          <button onClick={goCategories}
            className={`font-semibold transition-colors ${step === 1 ? "text-gray-900" : "text-blue-500 hover:text-blue-700 cursor-pointer"}`}>
            Categories
          </button>
          {category && (
            <>
              <span className="text-gray-300">/</span>
              <button onClick={goTypes} disabled={step === 2}
                className={`font-semibold transition-colors ${step === 2 ? "text-gray-900" : "text-blue-500 hover:text-blue-700 cursor-pointer"}`}>
                {category}
              </button>
            </>
          )}
          {typeId && (
            <>
              <span className="text-gray-300">/</span>
              <span className="font-semibold text-gray-900">{RATING_TYPE.label}</span>
            </>
          )}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">

          {/* Step 1 — pick a category */}
          {step === 1 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {QUESTION_BANK.map((cat) => {
                const addedInCat = cat.items.filter((i) => used.has(i.trim().toLowerCase())).length;
                return (
                  <button key={cat.name}
                    onClick={() => { setCategory(cat.name); setTypeId(null); }}
                    className="text-left px-4 py-3.5 rounded-xl border-2 border-gray-100 hover:border-blue-400 hover:bg-blue-50/50 transition-all cursor-pointer flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-gray-800 leading-snug">{cat.name}</p>
                      <p className="text-xs text-gray-400 mt-0.5">
                        {cat.items.length} questions{addedInCat ? ` · ${addedInCat} added` : ""}
                      </p>
                    </div>
                    <svg className="w-4 h-4 text-gray-300 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                    </svg>
                  </button>
                );
              })}
            </div>
          )}

          {/* Step 2 — pick an answer type (only Rating today) */}
          {step === 2 && activeCat && (
            <div className="grid grid-cols-1 gap-2.5">
              <button onClick={() => setTypeId(RATING_TYPE.id)}
                className="text-left px-5 py-4 rounded-xl border-2 border-gray-100 hover:border-amber-400 hover:bg-amber-50/50 transition-all cursor-pointer flex items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold text-amber-600 bg-amber-50 border border-amber-200 rounded-md px-2 py-0.5">★ {RATING_TYPE.label}</span>
                    <span className="text-xs text-gray-400">{activeCat.items.length} questions</span>
                  </div>
                  <p className="text-xs text-gray-400">{RATING_TYPE.scale}</p>
                </div>
                <svg className="w-4 h-4 text-gray-300 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </button>
              <p className="text-xs text-gray-300 px-1">More answer types will appear here as the framework grows.</p>
            </div>
          )}

          {/* Step 3 — pick questions */}
          {step === 3 && activeCat && (
            <>
              <div className="relative mb-3">
                <svg className="w-4 h-4 text-gray-300 absolute left-3 top-1/2 -translate-y-1/2" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M11 18a7 7 0 100-14 7 7 0 000 14z" />
                </svg>
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={`Search in ${activeCat.name}…`}
                  className="w-full text-sm border border-gray-200 rounded-lg pl-9 pr-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
                />
              </div>

              <div className="space-y-2">
                {questions.length === 0 ? (
                  <div className="text-center text-sm text-gray-400 py-12">No matching questions.</div>
                ) : (
                  questions.map((item) => {
                    const isUsed = used.has(item.trim().toLowerCase());
                    const disabled = isUsed || !canAdd;
                    return (
                      <button key={item}
                        disabled={disabled}
                        onClick={() => onSelect(bankItemToDraft(activeCat.name, item))}
                        className={`w-full text-left px-4 py-3 rounded-xl border transition-all group ${
                          disabled
                            ? "border-gray-100 bg-gray-50 cursor-not-allowed"
                            : "border-gray-100 hover:border-blue-300 hover:bg-blue-50/50 cursor-pointer"
                        }`}>
                        <div className="flex items-center justify-between gap-3">
                          <span className={`text-sm ${disabled ? "text-gray-400" : "text-gray-700"}`}>{item}</span>
                          <div className="flex items-center gap-2 shrink-0">
                            <span className="text-[10px] font-semibold text-amber-600 bg-amber-50 border border-amber-200 rounded-md px-1.5 py-0.5">★ {LIKERT_MIN}–{LIKERT_MAX}</span>
                            {isUsed ? (
                              <span className="text-[10px] font-semibold text-green-600 bg-green-50 border border-green-200 rounded-full px-2 py-0.5">Added</span>
                            ) : (
                              <span className="text-xs font-semibold text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity">Add →</span>
                            )}
                          </div>
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-gray-100 flex items-center justify-between">
          <p className="text-xs text-gray-400">
            {canAdd
              ? "Selected questions are added as-is (locked to the standard 5-point Likert scale)."
              : `Survey is full (${count}/${max}). Remove a question to add more.`}
          </p>
          <button onClick={onClose}
            className="px-4 py-2 rounded-lg border border-gray-200 text-xs font-semibold text-gray-500 hover:bg-gray-50 transition-colors cursor-pointer">
            {`Done (${count}/${max})`}
          </button>
        </div>
      </div>
    </div>
  );
}
