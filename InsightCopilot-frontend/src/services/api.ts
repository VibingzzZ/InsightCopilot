import { Conversation, Message } from '../types';
import { mockConversations } from '../data/mockData';

const BASE_URL = '/api';

function formatSentAt(isoString?: string): string {
  if (!isoString) return '--:--';
  const match = isoString.match(/(\d{2}:\d{2})/);
  return match ? match[1] : isoString;
}

function normalizeRole(role: string): 'buyer' | 'agent' | 'system' {
  if (role === 'agent') return 'agent';
  if (role === 'system') return 'system';
  return 'buyer'; // 'buyer' | 'customer' 均映射为前端的 'buyer'
}

export const api = {
  async getConversation(id: string): Promise<Conversation> {
    const convo = mockConversations.find(c => c.id === id);
    if (!convo) throw new Error('Not found');
    return convo;
  },

  async executeAction(conversationId: string, actionTitle: string): Promise<{ success: boolean; result: string }> {
    return { success: true, result: 'done' };
  },

  /**
   * 从后端拉取会话的历史消息记录
   */
  async fetchSessionMessages(sessionId: string): Promise<Message[]> {
    try {
      const response = await fetch(`${BASE_URL}/sessions/${sessionId}/messages?order=asc&page_size=100`);
      if (!response.ok) {
        console.warn(`[API] fetchSessionMessages failed with status ${response.status}, fallback to mock.`);
        return [];
      }
      const json = await response.json();
      const items = json?.data?.items;
      if (!Array.isArray(items)) {
        return [];
      }

      return items.map((item: any): Message => {
        return {
          id: item.message_id,
          role: normalizeRole(item.role),
          text: item.message_text || '',
          time: formatSentAt(item.sent_at),
          attachment: item.image_path ? (item.image_path.split('/').pop() || item.image_path) : undefined,
          contentType: item.content_type || 'text',
        };
      });
    } catch (err) {
      console.warn('[API] fetchSessionMessages request error:', err);
      return [];
    }
  },

  /**
   * 发送会话消息并持久化到数据库
   */
  async sendSessionMessage(
    sessionId: string,
    params: { role: 'agent' | 'buyer' | 'customer' | 'system'; content: string; sender_label?: string }
  ): Promise<any> {
    const response = await fetch(`${BASE_URL}/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        role: params.role,
        content: params.content,
        send: true,
        sender_label: params.sender_label,
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to send message: ${response.statusText}`);
    }

    return await response.json();
  },
};
