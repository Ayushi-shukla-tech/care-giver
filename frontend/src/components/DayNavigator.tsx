interface Props {
  dateString: string;
  onPrevious: () => void;
  onNext: () => void;
  nextDisabled: boolean;
}

function formatDateLabel(dateString: string): string {
  const [year, month, day] = dateString.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function DayNavigator({ dateString, onPrevious, onNext, nextDisabled }: Props) {
  return (
    <div className="mb-4 flex items-center justify-between">
      <button
        onClick={onPrevious}
        aria-label="Previous day"
        className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-2xl font-semibold text-slate-600 shadow-sm transition hover:bg-slate-100"
      >
        ←
      </button>
      <span className="text-lg font-semibold text-slate-800">{formatDateLabel(dateString)}</span>
      <button
        onClick={onNext}
        disabled={nextDisabled}
        aria-label="Next day"
        className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-2xl font-semibold text-slate-600 shadow-sm transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-30"
      >
        →
      </button>
    </div>
  );
}
