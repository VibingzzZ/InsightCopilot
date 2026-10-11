import { useState, useEffect } from 'react';
import { ChevronRight, Sparkles, AlertTriangle, CheckCircle2, ShieldAlert, Clock3, ShieldCheck, Check, TicketCheck, Loader2 } from 'lucide-react';
import { Conversation, Action } from '../../types';
import { useUIStore } from '../../store/useUIStore';
import { useChatStore } from '../../store/useChatStore';
import styles from './CopilotPane.module.css';

function SectionTitle({ children, action, onAction }: { children: string; action?: string; onAction?: () => void }) { 
  return (
    <div className={styles['section-title']}>
      <h3>{children}</h3>
      {action && <button onClick={onAction}>{action}<ChevronRight size={12} /></button>}
    </div>
  ); 
}

function InsightPanel({ conversation: c, onAccept }: { conversation: Conversation; onAccept: (draft: string) => void }) {
  const notify = useUIStore(state => state.notify);
  const remoteDraft = useChatStore(state => state.drafts[c.id]);
  const [draft, setDraft] = useState(remoteDraft || c.draft);
  const [isGenerating, setIsGenerating] = useState(false);

  // 当切换会话或后端推送了新草稿时，重置本地草稿
  useEffect(() => { setDraft(remoteDraft || c.draft); }, [c.id, c.draft, remoteDraft]);

  const handleRegenerate = (mode: 'remake' | 'tone') => {
    setIsGenerating(true);
    notify(mode === 'remake' ? '已向大模型发送重新生成草稿请求...' : '正在使用 AI 为您润色和调整语气...');
    
    // 模拟等待后端大模型返回
    setTimeout(() => {
      setDraft(mode === 'remake' 
        ? "非常抱歉给您带来如此困扰。我会立即为您建立专项工单并加急处理。在处理期间也请您务必遵医嘱妥善治疗，如果有任何新的情况随时联系我。"
        : "亲爱的，真的非常抱歉让您有这样的体验呢~ 已经火速为您升级给不良反应专员处理啦，明天上午专员会亲自联系您，请您安心休养哦~");
      setIsGenerating(false);
    }, 1500);
  };

  return (
    <>
      <section className={styles['copilot-section']}>
        <SectionTitle>当前判断</SectionTitle>
        <p className={styles['insight-copy']}>{c.insight}</p>
      </section>
      <section className={styles['copilot-section']}>
        <SectionTitle>已核验事实</SectionTitle>
        <dl className={styles.facts}>
          {c.facts.map(f => (
            <div key={f.label}>
              <dt>{f.label}</dt>
              <dd className={styles[f.tone]}>{f.value}</dd>
            </div>
          ))}
        </dl>
      </section>
      {c.promise && (
        <section className={styles['copilot-section']}>
          <SectionTitle>服务承诺</SectionTitle>
          <div className={`${styles['promise-card']} ${styles[c.risk]}`}>
            <div>
              <Clock3 size={16} />
              <section>
                <strong>{c.promise.title}</strong>
                <span>{c.promise.owner} · {c.promise.deadline}</span>
              </section>
            </div>
            <em>{c.promise.status}</em>
          </div>
        </section>
      )}
      <section className={styles['copilot-section']}>
        <SectionTitle action="重新生成" onAction={() => handleRegenerate('remake')}>回复草稿</SectionTitle>
        <div className={styles.draft}>
          <p>{isGenerating ? <span style={{display: 'flex', alignItems: 'center', gap: '6px', color: '#8993a1'}}><Loader2 size={12} style={{animation: 'spin 1s linear infinite'}}/> 正在思考中...</span> : draft}</p>
          <div>
            <button disabled={isGenerating} onClick={() => onAccept(draft)}><Check size={14} />采纳草稿</button>
            <button disabled={isGenerating} onClick={() => handleRegenerate('tone')}><Sparkles size={14} />调整语气</button>
          </div>
        </div>
      </section>
    </>
  );
}

function TimelinePanel({ conversation: c }: { conversation: Conversation }) { 
  const notify = useUIStore(state => state.notify);
  return (
    <section className={styles['copilot-section']}>
      <SectionTitle>消费者服务时间线</SectionTitle>
      <div className={styles.timeline}>
        {c.history.map((h, i) => (
          <div key={`${h.date}-${i}`} className={styles[h.tone]}>
            <i />
            <section>
              <time>{h.date}</time>
              <strong>{h.title}</strong>
              <p>{h.detail}</p>
            </section>
          </div>
        ))}
      </div>
    </section>
  ); 
}

const actionIcon = { ticket: TicketCheck, clock: Clock3, shield: ShieldAlert };

function ActionsPanel({ actions, onExecute, ticketCreated, completedActions, conversationId }: { actions: Action[]; onExecute: (a: Action) => void; ticketCreated: boolean; completedActions: Record<string, string>; conversationId: string }) { 
  const notify = useUIStore(state => state.notify);
  return (
    <section className={styles['copilot-section']}>
      <SectionTitle>建议动作</SectionTitle>
      <div className={styles['action-list']}>
        {actions.map(a => { 
          const Icon = actionIcon[a.icon]; 
          const done = completedActions[`${conversationId}:${a.title}`]; 
          return (
            <div className={styles['action-row']} key={a.title}>
              <div>
                <Icon size={17} />
                <section>
                  <strong>{a.title}</strong>
                  <p>{a.detail}</p>
                </section>
              </div>
              <button disabled={!!done} onClick={() => onExecute(a)}>
                {done ?? (ticketCreated && a.title.startsWith('创建') ? '已创建' : a.button)}
              </button>
            </div>
          );
        })}
      </div>
      <p className={styles['action-note']}><ShieldCheck size={14} />系统只生成操作草稿，敏感动作需要人工确认。</p>
    </section>
  ); 
}

export function CopilotPane({ conversation, onAcceptDraft }: { conversation: Conversation; onAcceptDraft: (draft: string) => void }) {
  const tab = useUIStore(state => state.tab);
  const setTab = useUIStore(state => state.setTab);
  
  const ticketCreated = useChatStore(state => !!state.ticketCreated[conversation.id]);
  const completedActions = useChatStore(state => state.completedActions);
  const markActionDone = useChatStore(state => state.markActionDone);
  const notify = useUIStore(state => state.notify);

  const executeAction = (action: Action) => {
    const createsTicket = action.title.startsWith('创建');
    markActionDone(conversation.id, action.title, createsTicket);
    notify(`${action.title}${createsTicket ? '已创建' : '已提交'}`);
  };

  return (
    <aside className={styles['copilot-pane']}>
      <div className={styles['copilot-header']}>
        <div>
          <span><Sparkles size={14} />AI COPILOT</span>
          <h2>智能客服</h2>
        </div>
        <div className={styles.live}><i />实时分析</div>
      </div>
      
      <div className={`${styles['risk-banner']} ${styles[conversation.risk]}`}>
        <div>
          {conversation.risk === 'urgent' ? <ShieldAlert /> : conversation.risk === 'attention' ? <AlertTriangle /> : <CheckCircle2 />}
        </div>
        <section>
          <strong>{conversation.risk === 'urgent' ? '紧急：消费者已就医' : conversation.risk === 'attention' ? '关注：历史承诺未完成' : '当前服务风险较低'}</strong>
          <p>{conversation.risk === 'urgent' ? '已触发 L3 不良反应处置流程' : conversation.risk === 'attention' ? '建议优先确认处理进度并明确反馈时间' : '按标准流程继续处理'}</p>
        </section>
      </div>
      
      <div className={styles['copilot-tabs']}>
        <button className={tab === 'insight' ? styles.active : ''} onClick={() => setTab('insight')}>洞察</button>
        <button className={tab === 'timeline' ? styles.active : ''} onClick={() => setTab('timeline')}>全轨迹</button>
        <button className={tab === 'actions' ? styles.active : ''} onClick={() => setTab('actions')}>动作</button>
      </div>
      
      <div className={styles['copilot-scroll']}>
        {tab === 'insight' && <InsightPanel conversation={conversation} onAccept={onAcceptDraft} />}
        {tab === 'timeline' && <TimelinePanel conversation={conversation} />}
        {tab === 'actions' && <ActionsPanel actions={conversation.actions} onExecute={executeAction} ticketCreated={ticketCreated} completedActions={completedActions} conversationId={conversation.id} />}
      </div>
    </aside>
  );
}
