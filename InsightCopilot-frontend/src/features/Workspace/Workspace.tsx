import { useMemo, useRef, useEffect, useState } from 'react';
import { Search, X, ListFilter, History, MoreHorizontal, ChevronRight, ChevronDown, Image, Paperclip, Sparkles, ShieldCheck, Send } from 'lucide-react';
import { useUIStore } from '../../store/useUIStore';
import { useChatStore } from '../../store/useChatStore';
import { mockConversations } from '../../data/mockData';
import { Avatar } from '../../components/Avatar';
import { MessageBubble } from '../../components/MessageBubble';
import { CopilotPane } from '../Copilot/CopilotPane';
import { agentSocket } from '../../services/socket';
import styles from './Workspace.module.css';

export function Workspace() {
  const queueFilter = useUIStore(state => state.queueFilter);
  const setQueueFilter = useUIStore(state => state.setQueueFilter);
  const query = useUIStore(state => state.query);
  const setQuery = useUIStore(state => state.setQuery);
  const productExpanded = useUIStore(state => state.productExpanded);
  const setProductExpanded = useUIStore(state => state.setProductExpanded);
  const setOverlay = useUIStore(state => state.setOverlay);
  const setSelectedAttachment = useUIStore(state => state.setSelectedAttachment);
  const setTab = useUIStore(state => state.setTab);
  const notify = useUIStore(state => state.notify);

  const selectedId = useChatStore(state => state.selectedId);
  const setSelectedId = useChatStore(state => state.setSelectedId);
  const messagesStore = useChatStore(state => state.messages);
  const addMessage = useChatStore(state => state.addMessage);

  const [composer, setComposer] = useState('');
  const messageStreamRef = useRef<HTMLDivElement>(null);

  const selected = mockConversations.find(c => c.id === selectedId) ?? mockConversations[0];
  
  const filtered = useMemo(() => mockConversations.filter(c => {
    const textMatch = `${c.customer}${c.order}${c.scene}${c.preview}${c.messages.map(m => m.text).join(' ')}`.toLowerCase().includes(query.toLowerCase());
    if (!textMatch) return false;
    if (queueFilter === 'risk') return c.risk !== 'normal';
    if (queueFilter === 'pending') return c.pending;
    return true;
  }), [queueFilter, query]);

  const allMessages = [...selected.messages, ...(messagesStore[selected.id] ?? [])];

  useEffect(() => {
    const stream = messageStreamRef.current;
    if (stream) stream.scrollTop = stream.scrollHeight;
  }, [selected.id, allMessages.length]);

  useEffect(() => {
    agentSocket.connect(selected.id);
    return () => agentSocket.disconnect();
  }, [selected.id]);

  const chooseConversation = (id: string) => { 
    setSelectedId(id); 
    setTab('insight'); 
    setComposer(''); 
    setProductExpanded(false); 
    setOverlay('none'); 
  };

  const sendMessage = () => {
    const text = composer.trim(); 
    if (!text) return;
    addMessage(selected.id, { role: 'agent', text, time: '刚刚' });
    agentSocket.sendMessage(text);
    setComposer(''); 
    notify(text.includes('明天') || text.includes('18:00') || text.includes('小时') ? '消息已发送，识别到 1 条服务承诺' : '消息已发送');
  };

  const ticketCreated = useChatStore(state => state.ticketCreated);

  return (
    <div className={styles['service-layout']}>
      {/* Queue Pane */}
      <section className={styles['queue-pane']}>
        <div className={styles['queue-title']}>
          <div>
            <span>在线接待</span>
            <h1>接待中 <em>{filtered.length}</em></h1>
          </div>
          <button title="筛选条件" onClick={() => notify('当前已按风险和时间排序')}><ListFilter size={17} /></button>
        </div>
        
        <label className={styles.search}>
          <Search size={15} />
          <input value={query} onChange={e => setQuery(e.target.value)} placeholder="联系人、订单号、聊天记录" />
          {query && <button onClick={() => setQuery('')}><X size={13} /></button>}
        </label>
        
        <div className={styles['queue-tabs']}>
          <button className={queueFilter === 'all' ? styles.active : ''} onClick={() => setQueueFilter('all')}>全部 <b>{mockConversations.length}</b></button>
          <button className={queueFilter === 'risk' ? styles.active : ''} onClick={() => setQueueFilter('risk')}>风险 <b>2</b></button>
          <button className={queueFilter === 'pending' ? styles.active : ''} onClick={() => setQueueFilter('pending')}>待跟进 <b>3</b></button>
        </div>
        
        <div className={styles['queue-section-label']}>
          <span>正在接待</span>
          <small>按风险排序</small>
        </div>
        
        <div className={styles['conversation-list']}>
          {filtered.length ? filtered.map(c => (
            <button key={c.id} className={`${styles['conversation-row']} ${selected.id === c.id ? styles.selected : ''}`} onClick={() => chooseConversation(c.id)}>
              <Avatar text={c.avatar} risk={c.risk} />
              <div className={styles['conversation-text']}>
                <div><strong>{c.customer}</strong><span>{c.time}</span></div>
                <p>{c.preview}</p>
                <small>{c.scene}</small>
              </div>
              {c.risk !== 'normal' && <i className={`${styles['risk-dot']} ${styles[c.risk]}`} />}
            </button>
          )) : (
            <div className={styles['empty-state']}>
              <Search size={18} />
              <strong>没有匹配的会话</strong>
              <span>请尝试联系人、订单号或聊天内容</span>
            </div>
          )}
        </div>
      </section>

      {/* Chat Pane */}
      <section className={styles['chat-pane']}>
        <div className={styles['chat-header']}>
          <div className={styles['customer-id']}>
            <Avatar text={selected.avatar} risk={selected.risk} />
            <div>
              <h2>{selected.customer}<i /></h2>
              <p>{selected.visits} 次服务记录 · 会话 {selected.id}</p>
            </div>
          </div>
          <div className={styles['chat-tools']}>
            <span className={`${styles['scene-tag']} ${styles[selected.risk]}`}>{selected.scene}</span>
            <button title="历史记录" onClick={() => setTab('timeline')}><History size={17} /></button>
            <button title="更多" onClick={() => notify('会话操作已就绪')}><MoreHorizontal size={19} /></button>
          </div>
        </div>
        
        <div className={styles['context-strip']}>
          <div><span>关联订单</span><strong>{selected.order}</strong></div>
          <div><span>关联工单</span><strong>{ticketCreated[selected.id] ? 'ADR-20260913 · 已创建' : selected.ticket}</strong></div>
          <div><span>情绪趋势</span><strong className={styles[selected.risk]}>{selected.emotion}</strong></div>
          <button onClick={() => setTab('timeline')}><span>完整轨迹</span><ChevronRight size={14} /></button>
        </div>
        
        <div className={`${styles['product-strip']} ${productExpanded ? styles.expanded : ''}`}>
          <img src="/product-card.png" alt="消费者正在咨询的美妆商品" />
          <div>
            <span>消费者正在咨询</span>
            <strong>{selected.id === 'S00015' ? '测试B5多效修护面膜 20片' : selected.id === 'S00005' ? '测试水润保湿眼霜 15ml' : selected.id === 'S00159' ? '测试会员加赠护理礼' : selected.sceneMinor}</strong>
            <small onClick={() => setOverlay('order')}>查看订单详情</small>
            {productExpanded && <p>订单 {selected.order} · {selected.ticket}</p>}
          </div>
          <button onClick={() => setProductExpanded(old => !old)}>{productExpanded ? '收起' : '展开'} <ChevronDown size={13} /></button>
        </div>
        
        <div className={styles['message-stream']} ref={messageStreamRef}>
          <div className={styles['date-divider']}><span>今天</span></div>
          {allMessages.map((m, idx) => (
            <MessageBubble 
              key={`${m.time}-${idx}`} 
              message={m} 
              customer={selected.customer} 
              onOpenAttachment={(name) => { setSelectedAttachment(name); setOverlay('attachment'); }} 
            />
          ))}
        </div>
        
        <div className={styles.composer}>
          <div className={styles['composer-bar']}>
            <button title="添加图片" onClick={() => notify('图片上传将在后端接入')}><Image size={18} /></button>
            <button title="添加附件" onClick={() => notify('附件上传将在后端接入')}><Paperclip size={18} /></button>
            <button title="AI 快捷指令" onClick={() => { setComposer(selected.draft); notify('已插入 AI 回复草稿'); }}><Sparkles size={18} /></button>
            <span><ShieldCheck size={13} />敏感信息已脱敏</span>
          </div>
          <textarea maxLength={500} value={composer} onChange={e => setComposer(e.target.value)} placeholder="输入回复，或采纳右侧 AI 草稿" />
          <div className={styles['composer-footer']}>
            <small>{composer.length}/500</small>
            <button className={styles['send-button']} onClick={sendMessage} disabled={!composer.trim()}>发送 <Send size={14} /></button>
          </div>
        </div>
      </section>

      {/* Copilot Pane */}
      <CopilotPane conversation={selected} onAcceptDraft={() => { setComposer(selected.draft); notify('草稿已放入输入框'); }} />
    </div>
  );
}
