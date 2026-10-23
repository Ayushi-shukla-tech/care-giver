const IST_TIME_ZONE = "Asia/Kolkata";

export function formatIstTime(isoString: string): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: IST_TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(isoString));
}

export function istDateString(date: Date): string {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: IST_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  // en-CA locale formats as YYYY-MM-DD directly.
  return formatter.format(date);
}

export function todayIstDateString(): string {
  return istDateString(new Date());
}

export function addDaysToIstDateString(dateString: string, deltaDays: number): string {
  const [year, month, day] = dateString.split("-").map(Number);
  const utcNoon = new Date(Date.UTC(year, month - 1, day, 12, 0, 0));
  utcNoon.setUTCDate(utcNoon.getUTCDate() + deltaDays);
  return istDateString(utcNoon);
}
