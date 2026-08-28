const BASE = "/api/v1";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(BASE + path, init);
  const j = await r.json();
  if (j.code && j.code !== 0) throw new Error(j.msg || "请求失败");
  return j.data as T;
}

export const api = {
  me: () => req<any>("/auth/me"),
  users: () => req<any[]>("/users"),
  dashboard: () => req<any>("/dashboard"),
  spaces: () => req<any[]>("/spaces"),
  space: (id: number) => req<any>(`/spaces/${id}`),
  createSpace: (body: any) => req<any>("/spaces", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  updateSpace: (id: number, body: any) => req<any>(`/spaces/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  syncSpace: (id: number) => req<any>(`/spaces/${id}/sync`, { method: "POST" }),
  spaceMeetings: (id: number) => req<any[]>(`/spaces/${id}/meetings`),
  meeting: (id: number) => req<any>(`/meetings/${id}`),
  transcript: (id: number) => req<any[]>(`/meetings/${id}/transcript`),
  importMeeting: (fd: FormData) => req<any>("/meetings/import", { method: "POST", body: fd }),
  feishuLink: (body: any) => req<any>("/meetings/feishu-link", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  dingtalkPull: (body: any) => req<any>("/meetings/dingtalk-pull", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  reExtract: (id: number) => req<any>(`/meetings/${id}/re-extract`, { method: "POST" }),
  confirm: (id: number) => req<any>(`/entities/${id}/confirm`, { method: "POST" }),
  editEntity: (id: number, payload: any) => req<any>(`/entities/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ payload }) }),
  deleteEntity: (id: number) => req<any>(`/entities/${id}`, { method: "DELETE" }),
  confirmAll: (id: number) => req<any>(`/meetings/${id}/confirm-all`, { method: "POST" }),
  addEntity: (mid: number, body: any) => req<any>(`/meetings/${mid}/entities`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  entities: (qs = "") => req<any[]>(`/entities${qs}`),
  revisions: (id: number) => req<any[]>(`/entities/${id}/revisions`),
  search: (q: string, spaceId?: number) => req<any[]>(`/search?q=${encodeURIComponent(q)}${spaceId ? `&space_id=${spaceId}` : ""}`),
  topics: (spaceId: number) => req<any[]>(`/topics?space_id=${spaceId}`),
  timeline: (id: number) => req<any>(`/topics/${id}/timeline`),
  reports: (spaceId?: number) => req<any[]>(`/reports${spaceId ? `?space_id=${spaceId}` : ""}`),
  report: (id: number) => req<any>(`/reports/${id}`),
  generateReport: (body: any) => req<any>("/reports/generate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  saveReport: (id: number, content_md: string) => req<any>(`/reports/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content_md }) }),
  sessions: () => req<any[]>("/agent/sessions"),
  createSession: (body: any) => req<any>("/agent/sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  session: (id: number) => req<any>(`/agent/sessions/${id}`),
  suggestions: (spaceId: number) => req<string[]>(`/agent/suggestions?space_id=${spaceId}`),
};
