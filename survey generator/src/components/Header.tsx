interface HeaderProps {
  count: number;
  max: number;
  onAdd: () => void;
  onGenerate: () => void;
  canAdd: boolean;
  isReady: boolean;
}

export default function Header({ count, max, onAdd, onGenerate, canAdd, isReady }: HeaderProps) {
  const pct = Math.round((count / max) * 100);

  return (
    <header className="bg-white border-b border-blue-100 shadow-sm sticky top-0 z-30">
      <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between gap-4">

        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center shrink-0">
            <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
            </svg>
          </div>
          <div>
            <h1 className="text-base font-bold text-gray-900 leading-tight">Survey Question Generator</h1>
            <p className="text-xs text-gray-400 leading-tight">Build your employee survey</p>
          </div>
        </div>

        {/* Progress + actions */}
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex flex-col items-end gap-1">
            <span className="text-xs font-semibold">
              <span className={isReady ? "text-green-600" : "text-blue-600"}>{count}</span>
              <span className="text-gray-400"> / {max} questions</span>
            </span>
            <div className="w-28 h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-300 ${isReady ? "bg-green-500" : "bg-blue-500"}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>

          {isReady ? (
            <button onClick={onGenerate}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-green-600 text-white text-xs font-semibold hover:bg-green-700 transition-colors cursor-pointer shadow-sm">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
              </svg>
              Generate Chatbot
            </button>
          ) : (
            <button onClick={onAdd} disabled={!canAdd}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer shadow-sm">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              Add Question
            </button>
          )}
        </div>
      </div>

      {isReady && (
        <div className="bg-green-50 border-t border-green-200 px-4 py-2 flex items-center justify-center gap-2">
          <svg className="w-4 h-4 text-green-600" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
          <span className="text-xs font-semibold text-green-700">
            All {max} questions ready — click <strong>Generate Chatbot</strong> to deploy.
          </span>
          <button onClick={onAdd} className="ml-2 text-xs text-green-600 underline hover:text-green-800 cursor-pointer">
            Edit questions
          </button>
        </div>
      )}
    </header>
  );
}
