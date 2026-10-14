import { useChatStore } from '../store/useChatStore';
import { useUIStore } from '../store/useUIStore';

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

  /** 发送结构化功能指令（任务 06）：如 adjust_tone / optimize_expression。 */
  sendCommand(command: string, params: Record<string, any> = {}, draft: string) {
    if (!this.currentConversationId || !this.socket || this.socket.readyState !== WebSocket.OPEN) {
      console.warn("Socket not ready, cannot send command");
      return;
    }
    this.socket.send(JSON.stringify({ command, params, draft }));
  }

  private handleIncomingEvent(payload: any) {
    // 分析生命周期：start → 进入「分析中」状态；done / error → 结束
    if (payload.type === 'start') {
      useUIStore.getState().setAnalyzing(true);
      return;
    }
    if (payload.type === 'done' || payload.type === 'error') {
      useUIStore.getState().setAnalyzing(false);
      return;
    }

    // 监听 LangGraph node updates
    if (payload.type === 'node_update' && payload.data) {
      // 获取到草稿节点时，将其更新为该会话的最新副驾草稿，并给出明确反馈
      if (payload.node === 'reply' && payload.data.reply_draft) {
        useChatStore.getState().setDraft(this.currentConversationId!, payload.data.reply_draft);
        useUIStore.getState().setAnalyzing(false);
        useUIStore.getState().notify('已生成回复草稿');
        console.log(`[LangGraph] 已回写回复草稿:`, payload.data.reply_draft);
      } else {
        console.log(`[LangGraph] Node updated:`, payload.node, payload.data);
      }
      return;
    }

    // 任务 06：轻量改写回写（adjust_tone / optimize_expression）
    if (payload.type === 'rewrite' && payload.rewritten) {
      useChatStore.getState().setDraft(this.currentConversationId!, payload.rewritten);
      console.log(`[Rewrite] ${payload.command}:`, payload.rewritten);
      return;
    }

    // 会话结束：后端回传本次 AI 消耗（token / 金额 / 调用次数 / 降级占比）
    if (payload.type === 'cost_summary' && payload.totals) {
      const t = payload.totals;
      const yuan = (typeof t.cost_yuan === 'number' ? t.cost_yuan : (t.cost_cent || 0) / 100).toFixed(4);
      const totalTokens = t.total_tokens || 0;
      const degradedPct = t.calls ? Math.round((t.degraded / t.calls) * 100) : 0;
      useUIStore.getState().notify(
        `本次 AI 消耗 ¥${yuan}（${t.calls} 次调用 / 共 ${totalTokens} tokens，降级 ${degradedPct}%）`
      );
      console.log(`[Cost] session=${payload.session_id}`, t);
      return;
    }

    // 任务 05：测试接口触发的分析结果广播
    if (payload.type === 'analysis' && payload.result?.draft_reply) {
      useChatStore.getState().setDraft(this.currentConversationId!, payload.result.draft_reply);
      console.log(`[Analysis] broadcast for ${payload.session_id}`);
      return;
    }

    if (payload.type === 'error') {
      console.warn(`[Socket] error frame:`, payload.code, payload.message);
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
