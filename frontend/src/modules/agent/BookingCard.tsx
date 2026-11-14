import React from "react";
import { AlertTriangle, CalendarCheck, CalendarClock, CalendarX, PhoneCall } from "lucide-react";
import { formatDateTime, formatTime } from "../../lib/format";
import { Button } from "../../lib/ui";
import type { Slot } from "../../lib/types";
import type { AgentEvent } from "./sse";

export type BookingView =
  | { kind: "confirmed"; slot: Slot }
  | { kind: "already_booked"; slot: Slot }
  | { kind: "cancelled"; slot: Slot }
  | { kind: "clash"; alternatives: Slot[] }
  | { kind: "past"; alternatives: Slot[] }
  | { kind: "calendar_down"; alternatives: Slot[] }
  | { kind: "callback" };

/** What a book_slot or cancel_booking result means for the student; null when it needs no card (e.g. an unknown slot). */
export function bookingFromEvent(e: AgentEvent): BookingView | null {
  if (e.type !== "tool_result") return null;
  const r = e.data.result ?? {};
  if (e.data.name === "cancel_booking") return e.data.ok && r.ok && r.slot ? { kind: "cancelled", slot: r.slot } : null;
  if (e.data.name !== "book_slot") return null;
  if (!e.data.ok) {
    if (r.fallback === "other_slots_available") return { kind: "calendar_down", alternatives: r.alternatives ?? [] };
    if (r.fallback === "counsellor_callback") return { kind: "callback" };
    return null;
  }
  if (r.ok && r.slot) return { kind: "confirmed", slot: r.slot };
  if (r.reason === "already_booked" && r.slot) return { kind: "already_booked", slot: r.slot };
  if (r.reason === "slot_taken") return { kind: "clash", alternatives: r.alternatives ?? [] };
  if (r.reason === "slot_in_past") return { kind: "past", alternatives: r.alternatives ?? [] };
  return null;
}

/**
 * The cards one reply should show. The agent may call a tool several times in a turn, so the same
 * outcome is shown once, and after a successful booking only it (and any cancellation before it) matters.
 */
export function bookingCards(views: BookingView[] = []): BookingView[] {
  const seen = new Set<string>();
  const unique = views.filter((v) => {
    const key = `${v.kind}:${"slot" in v ? v.slot.slot_id : "alternatives" in v ? v.alternatives.map((s) => s.slot_id).join(",") : ""}`;
    return seen.has(key) ? false : (seen.add(key), true);
  });
  const cancelled = unique.some((v) => v.kind === "cancelled");
  const settled = unique.filter((v) => v.kind === "confirmed" || v.kind === "cancelled");
  if (unique.some((v) => v.kind === "confirmed")) return settled;
  return cancelled ? unique.filter((v) => v.kind !== "already_booked") : unique;
}

export function bookThisMessage(slot: Slot): string {
  return `Please book the ${formatDateTime(slot.start)} session with ${slot.counsellor} (slot ${slot.slot_id}).`;
}

const SlotLine: React.FC<{ slot: Slot }> = ({ slot }) => (
  <p className="text-sm font-medium text-ink">
    {formatDateTime(slot.start)} – {formatTime(slot.end)} IST
    <span className="block text-xs font-normal text-ink-secondary">with {slot.counsellor}</span>
  </p>
);

const Alternatives: React.FC<{ slots: Slot[]; disabled: boolean; onBook: (slot: Slot) => void }> = ({ slots, disabled, onBook }) => {
  if (slots.length === 0) return <p className="text-xs text-ink-secondary">No other free sessions right now. A counsellor can help you find a time.</p>;
  return (
    <ul className="mt-2 space-y-1.5">
      {slots.map((s) => (
        <li key={s.slot_id} className="flex items-center justify-between gap-3 rounded-lg bg-surface border border-line px-3 py-2">
          <SlotLine slot={s} />
          <Button small variant="secondary" className="shrink-0" disabled={disabled} onClick={() => onBook(s)}>Book this</Button>
        </li>
      ))}
    </ul>
  );
};

export const BookingCard: React.FC<{ view: BookingView; disabled: boolean; onBook: (slot: Slot) => void }> = ({ view, disabled, onBook }) => {
  const box = "mt-3 rounded-xl border p-3.5 text-ink";
  const title = "flex items-center gap-1.5 text-13 font-semibold mb-1.5";
  switch (view.kind) {
    case "confirmed":
      return (
        <div className={`${box} border-success/40 bg-success-soft`}>
          <p className={`${title} text-success`}><CalendarCheck className="w-4 h-4" aria-hidden /> Session booked</p>
          <SlotLine slot={view.slot} />
        </div>
      );
    case "already_booked":
      return (
        <div className={`${box} border-info/30 bg-info-soft`}>
          <p className={`${title} text-info`}><CalendarClock className="w-4 h-4" aria-hidden /> You already have a session</p>
          <SlotLine slot={view.slot} />
        </div>
      );
    case "cancelled":
      return (
        <div className={`${box} border-line bg-subtle`}>
          <p className={`${title} text-ink-secondary`}><CalendarX className="w-4 h-4" aria-hidden /> Session cancelled</p>
          <SlotLine slot={view.slot} />
        </div>
      );
    case "callback":
      return (
        <div className={`${box} border-warning/30 bg-warning-soft`}>
          <p className={`${title} text-warning`}><PhoneCall className="w-4 h-4" aria-hidden /> Calendar unavailable</p>
          <p className="text-xs text-ink-secondary">Your request went to a counsellor, who will arrange a time with you.</p>
        </div>
      );
    default: {
      const heading = view.kind === "clash" ? "That session is taken. Nearest free sessions:"
        : view.kind === "past" ? "That time has passed. Nearest free sessions:"
        : "The calendar couldn't complete the booking. These sessions are open:";
      return (
        <div className={`${box} border-warning/30 bg-warning-soft`}>
          <p className={`${title} text-warning`}><AlertTriangle className="w-4 h-4" aria-hidden /> {heading}</p>
          <Alternatives slots={view.alternatives} disabled={disabled} onBook={onBook} />
        </div>
      );
    }
  }
};
