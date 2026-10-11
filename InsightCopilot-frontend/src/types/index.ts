export type Message = { 
  id?: string;
  role: 'buyer' | 'agent' | 'system'; 
  text: string; 
  time: string; 
  attachment?: string;
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
