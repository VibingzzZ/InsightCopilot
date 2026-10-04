import { useChatStore } from '../store/useChatStore';

/**
 * Manages WebSocket or Server-Sent Events (SSE) connection to the LangGraph Agent backend.
 * This allows receiving streamed updates for reasoning steps, new extracted facts, and draft generation.
 */
class AgentSocket {
  private socket: WebSocket | null = null;
  private currentConversationId: string | null = null;

  connect(conversationId: string) {
    if (this.socket) {
      this.disconnect();
    }
    
    this.currentConversationId = conversationId;
    
    // In a real app, connect to the FastAPI websocket endpoint:
    // this.socket = new WebSocket(`ws://localhost:8000/api/chat/stream/${conversationId}`);
    
    // this.socket.onmessage = (event) => {
    //   const data = JSON.parse(event.data);
    //   this.handleIncomingEvent(data);
    // };
    
    console.log(`[Socket] Connected to agent stream for ${conversationId} (Mock)`);
  }

  sendMessage(text: string) {
    if (!this.currentConversationId) return;
    
    // In a real app:
    // this.socket?.send(JSON.stringify({ text }));
    
    // Mocking an agent response after 1.5s
    setTimeout(() => {
      useChatStore.getState().addMessage(this.currentConversationId!, {
        role: 'agent',
        text: '这是一条来自 Mock WebSocket 延迟返回的测试消息，后端接入后将替换为大模型流式输出。',
        time: '刚刚'
      });
    }, 1500);
  }

  private handleIncomingEvent(data: any) {
    // Handle different node events from LangGraph
    // e.g., 'fact_extracted', 'draft_generated', 'risk_updated'
  }

  disconnect() {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.currentConversationId = null;
  }
}

export const agentSocket = new AgentSocket();
