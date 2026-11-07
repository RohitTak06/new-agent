import type { Lead, Tier } from "./types";
import type { Tone } from "./ui";

export const TIER_TONE: Record<Tier, Tone> = { hot: "red", warm: "amber", cold: "blue" };

export function isAnonymous(lead: Lead): boolean {
  return !lead.profile.name && !lead.profile.email && !lead.profile.phone;
}

/** Nobody can pass this person a message: no email or phone, so nothing reaches them outside an open chat. */
export function hasNoContact(lead: Lead): boolean {
  return !lead.profile.email && !lead.profile.phone;
}

export function leadName(lead: Lead): string {
  return lead.profile.name || lead.profile.email || (isAnonymous(lead) ? `Anonymous visitor #${lead.id}` : `Lead #${lead.id}`);
}
