import type { Question, QuestionType } from "../types/models";

const TYPE_META: Record<string, { label: string; cls: string }> = {
  single_selection:    { label: "Single Selection",    cls: "bg-blue-100 text-blue-700" },
  multiple_selection:  { label: "Multiple Selection",  cls: "bg-indigo-100 text-indigo-700" },
  distribution:        { label: "Distribution",        cls: "bg-cyan-100 text-cyan-700" },
  hours_distribution:  { label: "Hours Distribution",  cls: "bg-amber-100 text-amber-700" },
  number:              { label: "Number",              cls: "bg-violet-100 text-violet-700" },
  rating:              { label: "Rating",              cls: "bg-pink-100 text-pink-700" },
  percentage:          { label: "Percentage",          cls: "bg-green-100 text-green-700" },
  free_text:           { label: "Free Text",           cls: "bg-sky-100 text-sky-700" },
} satisfies Partial<Record<QuestionType, { label: string; cls: string }>>;

interface QuestionCardProps {
  question: Question;
  index: number;
  total: number;
  onEdit: () => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}

export default function QuestionCard({ question, index, total, onEdit, onDelete, onMoveUp, onMoveDown }: QuestionCardProps) {
  const tm = TYPE_META[question.type] ?? { label: question.type, cls: "bg-gray-100 text-gray-600" };
  const meta = question.metadata ?? {};
  const opts = question.options ?? [];

  return (
    <div className="group relative bg-white rounded-2xl border border-blue-100 shadow-sm hover:shadow-md transition-shadow px-5 py-4">
      <div className="flex items-start gap-4">

        {/* Index badge */}
        <div className="shrink-0 w-8 h-8 rounded-lg bg-blue-600 text-white text-xs font-bold flex items-center justify-center mt-0.5">
          {index + 1}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1.5">
            {question.category && (
              <span className="text-xs font-medium bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
                {question.category}
              </span>
            )}
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${tm.cls}`}>
              {tm.label}
            </span>
            {question.type === "distribution" && meta.distribution_mode && (
              <span className="text-xs italic text-gray-400">{meta.distribution_mode}</span>
            )}
            {meta.max_choices && (
              <span className="text-xs text-gray-400">max {meta.max_choices} choices</span>
            )}
            {(meta.min_value != null || meta.max_value != null) && (
              <span className="text-xs text-gray-400">
                {meta.min_value ?? "?"} – {meta.max_value ?? "?"}
              </span>
            )}
          </div>

          <p className="text-sm font-medium text-gray-800 leading-snug mb-2">{question.question}</p>

          {opts.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-2">
              {opts.map((o) => (
                <span key={o.code} className="inline-flex items-center gap-1 text-xs bg-blue-50 text-blue-700 border border-blue-100 px-2 py-0.5 rounded-full font-medium">
                  <span className="font-bold">{o.code}</span>
                  {o.label && <span className="text-blue-500">· {o.label}</span>}
                </span>
              ))}
            </div>
          )}

          {meta.expected_format && (
            <p className="text-xs font-mono text-gray-400 bg-gray-50 rounded px-2 py-1 inline-block">
              {meta.expected_format}
            </p>
          )}
        </div>

        {/* Actions (visible on hover) */}
        <div className="shrink-0 flex flex-col items-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="flex gap-1 mb-1">
            <button onClick={onEdit}
              className="p-1.5 rounded-lg text-blue-500 hover:bg-blue-50 transition-colors cursor-pointer"
              title="Edit">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536M9 11l6.586-6.586a2 2 0 012.828 2.828L11.828 13.828a2 2 0 01-1.414.586H8v-2.414a2 2 0 01.586-1.414z" />
              </svg>
            </button>
            <button onClick={onDelete}
              className="p-1.5 rounded-lg text-red-400 hover:bg-red-50 transition-colors cursor-pointer"
              title="Delete">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M9 7h6m-7 0a1 1 0 001-1h4a1 1 0 001 1m-6 0h6" />
              </svg>
            </button>
          </div>
          <div className="flex flex-col gap-0.5">
            <button onClick={onMoveUp} disabled={index === 0}
              className="p-1 rounded text-gray-300 hover:text-gray-500 disabled:opacity-20 cursor-pointer">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
              </svg>
            </button>
            <button onClick={onMoveDown} disabled={index === total - 1}
              className="p-1 rounded text-gray-300 hover:text-gray-500 disabled:opacity-20 cursor-pointer">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
