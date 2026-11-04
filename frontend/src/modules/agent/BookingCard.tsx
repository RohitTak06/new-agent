import React from "react";
import { AlertTriangle, CalendarCheck, CalendarClock, PhoneCall } from "lucide-react";
import { formatDateTime, formatTime } from "../../lib/format";
import { Button } from "../../lib/ui";
import type { Slot } from "../../lib/types";
import type { AgentEvent } from "./sse";

export type BookingView =
  | { kind: "confirmed"; slot: Slot }
  | { kind: "already_booked"; slot: Slot }
  | { kind: "clash"; alternatives: Slot[] }
  | { kind: "past"; alternatives: Slot[] }
  | { kind: "calendar_down"; alternatives: Slot[] }
  | { kind: "callback" };

/** What a book_slot tool result means for the student; null when it needs no card (e.g. an unknown slot). */
export function bookingFromEvent(e: AgentEvent): BookingView | null {
  if (e.type !== "tool_result" || e.data.name !== "book_slot") return null;
  const r = e.data.result ?? {};
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

export function bookThisMessage(slot: Slot): string {
  return `Please book the ${formatDateTime(slot.start)} session with ${slot.counsellor} (slot ${slot.slot_id}).`;
}

const SlotLine: React.FC<{ slot: Slot }> = ({ slot }) => (
  <p className="text-sm font-medium text-slate-800">
    {formatDateTime(slot.start)} – {formatTime(slot.end)} IST
    <span className="block text-xs font-normal text-slate-600">with {slot.counsellor}</span>
  </p>
);

const Alternatives: React.FC<{ slots: Slot[]; disabled: boolean; onBook: (slot: Slot) => void }> = ({ slots, disabled, onBook }) => {
  if (slots.length === 0) return <p className="text-xs text-slate-600">No other free sessions right now. A counsellor can help you find a time.</p>;
  return (
    <ul className="mt-2 space-y-1.5">
      {slots.map((s) => (
        <li key={s.slot_id} className="flex items-center justify-between gap-3 rounded-lg bg-white border border-slate-200 px-2.5 py-1.5">
          <SlotLine slot={s} />
          <Button small variant="secondary" className="shrink-0" disabled={disabled} onClick={() => onBook(s)}>Book this</Button>
        </li>
      ))}
    </ul>
  );
};

export const BookingCard: React.FC<{ view: BookingView; disabled: boolean; onBook: (slot: Slot) => void }> = ({ view, disabled, onBook }) => {
  const box = "mt-2 rounded-xl border p-3 text-slate-800";
  const title = "flex items-center gap-1.5 text-xs font-semibold mb-1";
  switch (view.kind) {
    case "confirmed":
      return (
        <div className={`${box} border-emerald-200 bg-emerald-50`}>
          <p className={`${title} text-emerald-800`}><CalendarCheck className="w-4 h-4" /> Session booked</p>
          <SlotLine slot={view.slot} />
        </div>
      );
    case "already_booked":
      return (
        <div className={`${box} border-blue-200 bg-blue-50`}>
          <p className={`${title} text-blue-800`}><CalendarClock className="w-4 h-4" /> You already have a session</p>
          <SlotLine slot={view.slot} />
        </div>
      );
    case "callback":
      return (
        <div className={`${box} border-amber-200 bg-amber-50`}>
          <p className={`${title} text-amber-800`}><PhoneCall className="w-4 h-4" /> Calendar unavailable</p>
          <p className="text-xs text-slate-700">Your request went to a counsellor, who will arrange a time with you.</p>
        </div>
      );
    default: {
      const heading = view.kind === "clash" ? "That session is taken. Nearest free sessions:"
        : view.kind === "past" ? "That time has passed. Nearest free sessions:"
        : "The calendar couldn't complete the booking. These sessions are open:";
      return (
        <div className={`${box} border-amber-200 bg-amber-50`}>
          <p className={`${title} text-amber-800`}><AlertTriangle className="w-4 h-4" /> {heading}</p>
          <Alternatives slots={view.alternatives} disabled={disabled} onBook={onBook} />
        </div>
      );
    }
  }
};
