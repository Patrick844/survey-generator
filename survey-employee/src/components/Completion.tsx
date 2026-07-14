export default function Completion({ onReset }: { onReset: () => void }) {
  return (
    <div className="bg-green-50 border border-green-200 rounded-2xl p-6 text-center">
      <div className="text-3xl mb-2">🎉</div>
      <p className="font-semibold text-green-800">Survey complete — thank you!</p>
      <p className="text-sm text-green-700 mt-1">
        Your responses have been recorded. You can safely close this window.
      </p>
      <button onClick={onReset} className="mt-4 text-sm text-green-700 underline hover:text-green-900">
        Take it again
      </button>
    </div>
  );
}
