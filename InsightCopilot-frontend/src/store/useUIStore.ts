import { create } from 'zustand';

interface UIState {
  queueFilter: 'all' | 'risk' | 'pending';
  query: string;
  tab: 'insight' | 'timeline' | 'actions';
  promiseFilter: 'all' | 'attention' | 'done';
  toast: string;
  overlay: 'none' | 'order' | 'attachment' | 'new-tracking' | 'module';
  selectedAttachment: string;
  productExpanded: boolean;
  scanDone: boolean;

  setQueueFilter: (filter: 'all' | 'risk' | 'pending') => void;
  setQuery: (query: string) => void;
  setTab: (tab: 'insight' | 'timeline' | 'actions') => void;
  setPromiseFilter: (filter: 'all' | 'attention' | 'done') => void;
  setOverlay: (overlay: 'none' | 'order' | 'attachment' | 'new-tracking' | 'module') => void;
  setSelectedAttachment: (attachment: string) => void;
  setProductExpanded: (expanded: boolean | ((prev: boolean) => boolean)) => void;
  setScanDone: (done: boolean) => void;
  notify: (msg: string) => void;
}

export const useUIStore = create<UIState>((set) => ({
  queueFilter: 'all',
  query: '',
  tab: 'insight',
  promiseFilter: 'all',
  toast: '',
  overlay: 'none',
  selectedAttachment: '',
  productExpanded: false,
  scanDone: false,

  setQueueFilter: (f) => set({ queueFilter: f }),
  setQuery: (q) => set({ query: q }),
  setTab: (t) => set({ tab: t }),
  setPromiseFilter: (f) => set({ promiseFilter: f }),
  setOverlay: (o) => set({ overlay: o }),
  setSelectedAttachment: (a) => set({ selectedAttachment: a }),
  setProductExpanded: (e) => set((state) => ({ productExpanded: typeof e === 'function' ? e(state.productExpanded) : e })),
  setScanDone: (d) => set({ scanDone: d }),
  notify: (msg) => {
    set({ toast: msg });
    setTimeout(() => set({ toast: '' }), 2200);
  },
}));
