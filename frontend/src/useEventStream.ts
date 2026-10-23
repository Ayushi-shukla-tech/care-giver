import { useEffect } from "react";
import { getToken } from "./api";

export interface ReminderStreamEvent {
  type: string;
  reminder_event_id: string;
}

export function useEventStream(patientId: string, onEvent: (event: ReminderStreamEvent) => void) {
  useEffect(() => {
    const token = getToken();
    if (!token) return;

    const source = new EventSource(
      `http://localhost:8001/api/v1/patients/${patientId}/events/stream?token=${encodeURIComponent(token)}`
    );

    source.onmessage = (message) => {
      const event = JSON.parse(message.data) as ReminderStreamEvent;
      onEvent(event);
    };

    return () => source.close();
  }, [patientId, onEvent]);
}
