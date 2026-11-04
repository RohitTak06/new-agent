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
