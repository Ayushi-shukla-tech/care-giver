import { useState } from "react";

interface Props {
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
}

function BellIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 448 512" fill="currentColor" className={className}>
      <path d="M224 0c-17.7 0-32 14.3-32 32V49.9C119.5 61.4 64 124.2 64 200v33.4c0 45.4-15.5 89.5-43.8 124.9L5.3 377c-5.8 7.2-6.9 17.1-2.9 25.4S14.8 416 24 416H424c9.2 0 17.6-5.3 21.6-13.6s2.9-18.2-2.9-25.4l-14.9-18.6C399.5 322.9 384 278.8 384 233.4V200c0-75.8-55.5-138.6-128-150.1V32c0-17.7-14.3-32-32-32zm0 96h8c57.4 0 104 46.6 104 104v33.4c0 47.9 13.9 94.6 39.7 134.6H72.3C98.1 328 112 281.3 112 233.4V200c0-57.4 46.6-104 104-104h8zm64 352H224 160c0 17 6.7 33.3 18.7 45.3S207 512 224 512s33.3-6.7 45.3-18.7S288 465 288 448z" />
    </svg>
  );
}

function BellRingingIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 512 512" fill="currentColor" className={className}>
      <path d="M224 0c-17.7 0-32 14.3-32 32V51.2C119.5 66.4 64 130.2 64 208v32.9c0 25.9-8.4 51.2-24 71.9L5.3 353c-5.8 7.2-6.9 17.1-2.9 25.4S14.8 392 24 392H424c9.2 0 17.6-5.3 21.6-13.6s2.9-18.2-2.9-25.4l-34.7-40.2c-15.6-20.7-24-46-24-71.9V208c0-77.8-55.5-141.6-128-156.8V32c0-17.7-14.3-32-32-32H224zM24 224c0-4.4-3.6-8-8-8H8c-4.4 0-8 3.6-8 8v0c0 4.4 3.6 8 8 8h8c4.4 0 8-3.6 8-8zM100.3 121c6.7-11.8 14.5-22.9 23.3-33.2C87.2 116.5 60.5 156.7 49.4 203c-1 4.3-5.3 6.9-9.6 5.9s-6.9-5.3-5.9-9.6c11.7-49.2 40-91.6 78.4-121.3zM488 224c0-4.4 3.6-8 8-8h8c4.4 0 8 3.6 8 8v0c0 4.4-3.6 8-8 8h-8c-4.4 0-8-3.6-8-8zM394.9 87.8c8.9 10.3 16.6 21.4 23.3 33.2c38.5 29.7 66.7 72.1 78.4 121.3c1 4.3-1.6 8.6-5.9 9.6s-8.6-1.6-9.6-5.9c-11.1-46.3-37.8-86.5-74.2-115.2z" />
      <path d="M224 448c0 17 6.7 33.3 18.7 45.3S271 512 288 512s33.3-6.7 45.3-18.7S352 465 352 448H224z" />
    </svg>
  );
}

export function attemptUnlockAudioAndSpeech(): void {
  const silentTone = new Audio(
    "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA="
  );
  silentTone.volume = 0.01;
  silentTone.play().catch(() => {});

  const utterance = new SpeechSynthesisUtterance(" ");
  window.speechSynthesis.speak(utterance);
}

export default function EnableRemindersBanner({ enabled, onToggle }: Props) {
  const [justToggled, setJustToggled] = useState(false);

  function handleTap() {
    if (!enabled) {
      attemptUnlockAudioAndSpeech();
    }
    onToggle(!enabled);
    setJustToggled(true);
    setTimeout(() => setJustToggled(false), 500);
  }

  return (
    <button
      onClick={handleTap}
      aria-label={enabled ? "Turn off reminder sound" : "Turn on reminder sound"}
      title={enabled ? "Turn off reminder sound" : "Turn on reminder sound"}
      className={`flex h-14 w-14 items-center justify-center rounded-full border shadow-sm transition ${
        enabled
          ? "border-teal-300 bg-teal-50 text-teal-700"
          : "border-slate-200 bg-white text-slate-500 hover:bg-slate-50"
      } ${justToggled ? "animate-bell-shake" : ""}`}
    >
      {enabled ? <BellRingingIcon className="h-7 w-7" /> : <BellIcon className="h-7 w-7" />}
    </button>
  );
}
