import { Conversation } from '../types';
import { mockConversations } from '../data/mockData';

// Fetch initial data from our local mock mapping, avoiding the need for backend REST for initial UI shell load.
export const api = {
  async getConversation(id: string): Promise<Conversation> {
    const convo = mockConversations.find(c => c.id === id);
    if (!convo) throw new Error('Not found');
    return convo;
  },

  async executeAction(conversationId: string, actionTitle: string): Promise<{ success: boolean; result: string }> {
    return { success: true, result: 'done' };
  }
};
