/** Times from the API are shown in IST, the timezone every slot and follow-up is defined in. */
const TZ = "Asia/Kolkata";

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-IN", {
    timeZone: TZ, weekday: "short", day: "2-digit", month: "short", hour: "numeric", minute: "2-digit", hour12: true,
  });
}

export function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString("en-IN", { timeZone: TZ, hour: "numeric", minute: "2-digit", hour12: true });
}

/** "Thu, 05 Nov" for a YYYY-MM-DD date in IST. */
export function formatDay(day: string): string {
  return new Date(`${day}T12:00:00+05:30`).toLocaleDateString("en-IN", { timeZone: TZ, weekday: "short", day: "2-digit", month: "short" });
}

/** The IST date `days` after a YYYY-MM-DD date. */
export function addDays(day: string, days: number): string {
  const later = new Date(new Date(`${day}T12:00:00+05:30`).getTime() + days * 86_400_000);
  return later.toLocaleDateString("en-CA", { timeZone: TZ });
}
