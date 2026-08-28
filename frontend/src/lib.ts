export type Entity = {
  id: number;
  meeting_id: number;
  space_id: number;
  topic_id?: number | null;
  type: "decision" | "commitment" | "risk" | string;
  payload: Record<string, any>;
  anchor_segment_ids: number[];
  status: string;
  auto_committed: boolean;
  confidence?: number | null;
};

export function entityTitle(e: { payload?: Record<string, any>; type?: string }) {
  const p = e.payload || {};
  return p.conclusion || p.item || p.description || "未命名实体";
}

export function fmtDate(iso?: string) {
  if (!iso) return "";
  return iso.slice(0, 16).replace("T", " ");
}

export function fmtMs(ms?: number | null) {
  if (ms == null) return "";
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function emptyPayload(type: string) {
  if (type === "commitment") return { item: "", owner: "", due_date: "", deliverable: "" };
  if (type === "risk") return { description: "", raiser: "", impact: "" };
  return { conclusion: "", decider: "", rationale: "", alternatives: [] as string[] };
}
