// 承诺服务：对接后端「服务承诺跟踪」接口（GET /api/promises、POST /api/promises/scan）。
// 后端统一信封为 {data, meta, error}，承诺列表在 data.items 中。

const API_BASE = 'http://localhost:8000';

export interface PromiseRow {
  promise_id: string;
  session_id: string;
  customer_name_masked: string | null;
  customer_id: string;
  promise_type: string;
  statement: string;
  due_at: string | null;
  status: string;
  remaining_seconds: number | null;
  owner_type: string;
  owner_id: string | null;
  risk_level: string | null;
  source_message_id: string;
}

export interface PromiseFilter {
  status?: string;
  overdue?: boolean;
}

export async function fetchPromises(filter?: PromiseFilter): Promise<PromiseRow[]> {
  const params = new URLSearchParams();
  if (filter?.status) params.set('status', filter.status);
  if (filter?.overdue) params.set('overdue', 'true');
  const qs = params.toString();
  const res = await fetch(`${API_BASE}/api/promises${qs ? `?${qs}` : ''}`);
  const json = await res.json();
  if (!res.ok || json.error) {
    throw new Error(json?.error?.message || `加载承诺失败（HTTP ${res.status}）`);
  }
  return (json.data?.items ?? []) as PromiseRow[];
}

export async function scanPromises(): Promise<{ scanned: number; changed: number }> {
  const res = await fetch(`${API_BASE}/api/promises/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  const json = await res.json();
  if (!res.ok || json.error) {
    throw new Error(json?.error?.message || '扫描失败');
  }
  return (json.data ?? { scanned: 0, changed: 0 }) as { scanned: number; changed: number };
}
