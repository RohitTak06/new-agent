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

export interface LeadProfile {
  name: string | null;
  phone: string | null;
  email: string | null;
  city: string | null;
  program_interest: string | null;
  twelfth_percent: number | null;
  entrance_exam: string | null;
  budget_lakh: number | null;
  asked_scholarship: boolean;
  channel: Channel;
}

export interface Lead {
  id: number;
  profile: LeadProfile;
  score: LeadScore | null;
  status: string;
  opted_out: boolean;
}

export interface Approval {
  id: number;
  action: string;
  payload: Record<string, any>;
  status: "pending" | "approved" | "rejected";
  lead_id: number | null;
  reason: string | null;
  requested_by_actor: string;
  resolved_by: number | null;
  resolved_at: string | null;
  created_at: string;
}

export interface Followup {
  id: number;
  lead_id: number;
  due_at: string;
  template: string;
  status: "pending" | "sent" | "skipped" | "failed";
  payload: Record<string, any> | null;
  sent_message_id: number | null;
  processed_at: string | null;
}

export interface AuditRow {
  id: number;
  created_at: string;
  actor: string;
  event_type: string;
  tool_name: string | null;
  input: unknown;
  output: unknown;
  reasoning_step: string | null;
  approval_id: number | null;
  request_id: string | null;
  lead_id: number | null;
  session_id: string | null;
}
