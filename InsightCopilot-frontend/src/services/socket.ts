import { useChatStore } from '../store/useChatStore';

class AgentSocket {
  private socket: WebSocket | null = null;
  private currentConversationId: string | null = null;

  connect(conversationId: string) {
    if (this.socket) {
      this.disconnect();
    }
    
    this.currentConversationId = conversationId;
    
    // Connect to FastAPI WebSocket backend
    this.socket = new WebSocket(`ws://localhost:8000/api/chat/stream/${conversationId}`);
    
    this.socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleIncomingEvent(data);
    };
    
    this.socket.onopen = () => console.log(`[Socket] Connected to agent stream for ${conversationId}`);
    this.socket.onerror = (e) => console.error('[Socket] Connection error:', e);
  }

  sendMessage(text: string) {
    if (!this.currentConversationId || !this.socket || this.socket.readyState !== WebSocket.OPEN) {
      console.warn("Socket not ready, fallback to UI store update");
      return;
    }
    
    // Send message to the graph
    this.socket.send(JSON.stringify({ text }));
  }

  private handleIncomingEvent(payload: any) {
    // 监听 LangGraph node updates
    if (payload.type === 'node_update' && payload.data) {
      // 获取到草稿节点时，将其更新为该会话的最新副驾草稿
      if (payload.node === 'reply' && payload.data.reply_draft) {
        useChatStore.getState().setDraft(this.currentConversationId!, payload.data.reply_draft);
      }
      // 未来可以在 useUIStore 增加状态提示如 "正在分析情感..." "正在事实校验..."
      console.log(`[LangGraph] Node updated:`, payload.node, payload.data);
    }
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
