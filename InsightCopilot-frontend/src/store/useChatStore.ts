import { create } from 'zustand';
import { Message, PromiseRow } from '../types';

interface ChatState {
  selectedId: string;
  messages: Record<string, Message[]>;
  ticketCreated: Record<string, boolean>;
  completedActions: Record<string, string>;
  customPromises: PromiseRow[];
  drafts: Record<string, string>;
  
  setSelectedId: (id: string) => void;
  addMessage: (conversationId: string, message: Message) => void;
  setDraft: (conversationId: string, draft: string) => void;
  markActionDone: (conversationId: string, actionTitle: string, createsTicket: boolean) => void;
  addCustomPromise: (promise: PromiseRow) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  selectedId: 'S00015',
  messages: {},
  ticketCreated: {},
  completedActions: {},
  customPromises: [],
  drafts: {},

  setSelectedId: (id) => set({ selectedId: id }),
  addMessage: (conversationId, message) => set((state) => ({
    messages: {
      ...state.messages,
      [conversationId]: [...(state.messages[conversationId] || []), message],
    },
  })),
  setDraft: (conversationId, draft) => set((state) => ({
    drafts: {
      ...state.drafts,
      [conversationId]: draft
    }
  })),
  markActionDone: (conversationId, actionTitle, createsTicket) => set((state) => {
    const key = `${conversationId}:${actionTitle}`;
    return {
      ticketCreated: createsTicket ? { ...state.ticketCreated, [conversationId]: true } : state.ticketCreated,
      completedActions: { ...state.completedActions, [key]: createsTicket ? '已创建' : '已完成' },
    };
  }),
  addCustomPromise: (promise) => set((state) => ({
    customPromises: [...state.customPromises, promise],
  })),
}));
