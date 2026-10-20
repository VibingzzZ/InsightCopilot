import type { AttachmentKind } from '../types';

// 上传服务：对接后端 POST /api/uploads（multipart/form-data）。
// 成功返回统一信封的 data 字段；失败抛出可读错误（来自后端 {error:{message}}）。

const API_BASE = 'http://localhost:8000';

export interface UploadResult {
  id: string;
  url: string;
  path: string;
  filename: string;
  original_name: string;
  size: number;
  content_type: string;
  kind: AttachmentKind;
}

export interface UploadErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export async function uploadFile(file: File, kind: AttachmentKind): Promise<UploadResult> {
  const form = new FormData();
  form.append('file', file);
  form.append('kind', kind);

  const res = await fetch(`${API_BASE}/api/uploads`, {
    method: 'POST',
    body: form,
  });

  let json: { data: UploadResult | null; meta: unknown; error: UploadErrorBody | null } = {
    data: null,
    meta: null,
    error: null,
  };
  try {
    json = await res.json();
  } catch {
    throw new Error(`上传失败（HTTP ${res.status}，响应无法解析）`);
  }

  if (!res.ok || json.error) {
    throw new Error(json.error?.message || `上传失败（HTTP ${res.status}）`);
  }
  if (!json.data) {
    throw new Error('上传成功但未返回文件信息');
  }
  return json.data;
}
