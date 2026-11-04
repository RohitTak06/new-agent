/** API shapes used by the screens. These mirror backend/app/contracts/models.py and the routers. */
export type Role = "admin" | "counsellor" | "student";
export type Channel = "web" | "whatsapp" | "email";
export type Tier = "hot" | "warm" | "cold";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  lead_id: number | null;
}

export interface Slot {
  slot_id: string;
  counsellor: string;
  start: string;
  end: string;
}

export interface Booking extends Slot {
  lead_id: number;
  lead_name: string | null;
  upcoming: boolean;
}

export interface LeadScore {
  score: number;
  tier: Tier;
  reasons: string[];
}

export interface Chunk {
  text: string;
  source: string;
  score: number;
}

export interface Interaction {
  id: number;
  lead_id: number;
  actor: string;
  channel: Channel;
  direction: "inbound" | "outbound";
  message: string;
  meta: Record<string, any> | null;
  created_at: string;
}

export interface ChannelMessage {
  id: number;
  lead_id: number;
  channel: Channel;
  direction: "inbound" | "outbound";
  text: string;
  sent_at: string;
  created_at: string;
  meta: Record<string, any> | null;
}
