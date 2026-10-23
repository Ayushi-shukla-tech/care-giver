import { useCallback, useEffect, useRef, useState } from "react";
import { patientTodaysReminders } from "./api";
import type { ReminderEvent } from "./api";

const POLL_INTERVAL_MS = 7_000;
const ALARM_REPEAT_MS = 30_000;
const SNOOZE_DURATION_MS = 5 * 60_000;

const ACTIONABLE_STATUSES = new Set(["pending", "alarm_fired", "call_placed"]);

function playChime(): void {
  const audio = new Audio(
    "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA="
  );
  audio.play().catch(() => {
    // Autoplay may still be blocked in rare cases; failing silently is
    // acceptable since the gate is meant to have already unlocked this.
  });
}

function speak(text: string): void {
  const utterance = new SpeechSynthesisUtterance(text);
  window.speechSynthesis.speak(utterance);
}

export function useReminderAlarm(patientId: string, soundEnabled: boolean) {
  const [reminders, setReminders] = useState<ReminderEvent[]>([]);
  const [alarmingIds, setAlarmingIds] = useState<Set<string>>(new Set());
  const [snoozedUntil, setSnoozedUntil] = useState<Map<string, number>>(new Map());
  const lastAlarmedAtRef = useRef<Map<string, number>>(new Map());

  const refresh = useCallback(() => {
    if (!patientId) return;
    patientTodaysReminders(patientId).then(setReminders);
  }, [patientId]);

  useEffect(() => {
    if (!patientId) return;
    refresh();
    const interval = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [patientId, refresh]);

  useEffect(() => {
    if (!soundEnabled) return;

    const now = Date.now();
    const nextAlarming = new Set<string>();

    for (const reminder of reminders) {
      if (!ACTIONABLE_STATUSES.has(reminder.status)) continue;
      const scheduledAt = new Date(reminder.scheduled_at).getTime();
      if (scheduledAt > now) continue;

      const snoozeUntil = snoozedUntil.get(reminder.id);
      if (snoozeUntil && snoozeUntil > now) continue;

      nextAlarming.add(reminder.id);

      const lastAlarmed = lastAlarmedAtRef.current.get(reminder.id) ?? 0;
      if (now - lastAlarmed >= ALARM_REPEAT_MS) {
        playChime();
        speak(`Time to take your ${reminder.medicine_name}, ${reminder.medicine_dose}`);
        lastAlarmedAtRef.current.set(reminder.id, now);
      }
    }

    setAlarmingIds(nextAlarming);
  }, [soundEnabled, reminders, snoozedUntil]);

  const snooze = useCallback((reminderId: string) => {
    setSnoozedUntil((prev) => {
      const next = new Map(prev);
      next.set(reminderId, Date.now() + SNOOZE_DURATION_MS);
      return next;
    });
  }, []);

  const snoozedIds = new Set(
    Array.from(snoozedUntil.entries())
      .filter(([, until]) => until > Date.now())
      .map(([id]) => id)
  );

  return { reminders, alarmingIds, snoozedIds, snooze, refresh };
}
