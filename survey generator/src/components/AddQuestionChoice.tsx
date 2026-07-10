interface AddQuestionChoiceProps {
  onBlank: () => void;
  onLibrary: () => void;
  onClose: () => void;
}

export default function AddQuestionChoice({ onBlank, onLibrary, onClose }: AddQuestionChoiceProps) {
  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-bold text-gray-900">Add a Question</h2>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors cursor-pointer">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="px-6 py-5 grid grid-cols-1 gap-3">
          {/* From library */}
          <button onClick={onLibrary}
            className="text-left px-5 py-4 rounded-xl border-2 border-gray-100 hover:border-blue-400 hover:bg-blue-50/50 transition-all cursor-pointer">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-lg leading-none">📚</span>
              <span className="text-sm font-bold text-gray-900">Choose from library</span>
            </div>
            <p className="text-xs text-gray-400 leading-snug">
              Pick from the 300-item Work Dynamics framework (10 categories, validated 5-point Likert). Prefilled and editable.
            </p>
          </button>

          {/* Blank */}
          <button onClick={onBlank}
            className="text-left px-5 py-4 rounded-xl border-2 border-gray-100 hover:border-blue-400 hover:bg-blue-50/50 transition-all cursor-pointer">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-lg leading-none">✎</span>
              <span className="text-sm font-bold text-gray-900">Create from scratch</span>
            </div>
            <p className="text-xs text-gray-400 leading-snug">
              Write a custom question and choose any answer type (rating, selection, distribution, free text…).
            </p>
          </button>
        </div>
      </div>
    </div>
  );
}
