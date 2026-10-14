// 附件类型：图片（内联预览）或通用附件（文件卡片 / 弹窗预览）
export type AttachmentKind = 'image' | 'attachment';

export type Message = { 
  id?: string;
  role: 'buyer' | 'agent' | 'system'; 
  text: string; 
  time: string; 
  // 兼容旧版 mock：仅文件名（无真实 URL 时的占位展示）
  attachment?: string;
  // 上传后端后可直接访问的 URL（/media/... 或 http(s)://...）
  attachmentUrl?: string;
  // 附件类型，决定渲染方式
  attachmentKind?: AttachmentKind;
  contentType?: string;
}

export type Fact = { 
  label: string; 
  value: string; 
  tone?: 'danger' | 'warning' | 'success' 
}

export type Action = { 
  icon: 'ticket' | 'clock' | 'shield'; 
  title: string; 
  detail: string; 
  button: string 
}

export type Conversation = {
  id: string; 
  customer: string; 
  avatar: string; 
  preview: string; 
  time: string;
  scene: string; 
  risk: 'normal' | 'attention' | 'urgent'; 
  pending: boolean;
  order: string; 
  ticket: string; 
  emotion: string; 
  visits: number;
  messages: Message[]; 
  insight: string; 
  facts: Fact[]; 
  actions: Action[];
  draft: string; 
  promise?: { title: string; deadline: string; owner: string; status: string };
  history: { date: string; title: string; detail: string; tone?: string }[];
}

export type SourceSession = {
  id: string; 
  customer: string; 
  sceneMajor: string; 
  sceneMinor: string; 
  lastTime: string;
  preview: string; 
  hasImage: boolean; 
  orderIds: string[]; 
  ticketIds: string[];
  messages: Message[];
  orders: Record<string, unknown>[]; 
  tickets: Record<string, unknown>[];
}

export type PromiseRow = { 
  customer: string; 
  item: string; 
  biz: string; 
  deadline: string; 
  status: 'urgent' | 'due' | 'active' | 'done'; 
  owner: string 
}
