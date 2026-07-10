import type { Question } from "../types/models";
import QuestionCard from "./QuestionCard";

interface QuestionListProps {
  questions: Question[];
  onEdit: (q: Question) => void;
  onDelete: (id: string) => void;
  onMove: (id: string, dir: -1 | 1) => void;
  onAdd: () => void;
  canAdd: boolean;
}

export default function QuestionList({ questions, onEdit, onDelete, onMove, onAdd, canAdd }: QuestionListProps) {
  if (questions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-6">
        <div className="w-20 h-20 rounded-2xl bg-blue-100 flex items-center justify-center">
          <svg className="w-10 h-10 text-blue-400" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
        </div>
        <div className="text-center">
          <h2 className="text-lg font-semibold text-gray-700 mb-1">No questions yet</h2>
          <p className="text-sm text-gray-400">Start building your employee survey by adding your first question.</p>
        </div>
        <button
          onClick={onAdd}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-colors shadow-sm cursor-pointer"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          Add First Question
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {questions.map((q, i) => (
        <QuestionCard
          key={q.id}
          question={q}
          index={i}
          total={questions.length}
          onEdit={() => onEdit(q)}
          onDelete={() => onDelete(q.id)}
          onMoveUp={() => onMove(q.id, -1)}
          onMoveDown={() => onMove(q.id, 1)}
        />
      ))}

      {canAdd && (
        <button
          onClick={onAdd}
          className="mt-2 w-full flex items-center justify-center gap-2 py-4 rounded-xl border-2 border-dashed border-blue-200 text-blue-400 text-sm font-medium hover:border-blue-400 hover:text-blue-600 hover:bg-blue-50 transition-all cursor-pointer"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          Add Another Question
        </button>
      )}
    </div>
  );
}
