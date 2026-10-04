import { Conversation, Message } from '../types';

// Mock delay to simulate network request
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export const api = {
  /**
   * Fetches the conversation details including history, orders, and tickets.
   */
  async getConversation(id: string): Promise<Conversation> {
    await delay(500);
    // In a real app, this would be: 
    // const res = await fetch(`/api/conversations/${id}`);
    // return res.json();
    throw new Error('Not implemented: requires backend integration');
  },

  /**
   * Submits an action (e.g., creating a ticket or upgrading risk level).
   */
  async executeAction(conversationId: string, actionTitle: string): Promise<{ success: boolean; result: string }> {
    await delay(300);
    // In a real app:
    // const res = await fetch(`/api/conversations/${conversationId}/actions`, {
    //   method: 'POST',
    //   body: JSON.stringify({ action: actionTitle })
    // });
    // return res.json();
    return { success: true, result: 'done' };
  }
};
