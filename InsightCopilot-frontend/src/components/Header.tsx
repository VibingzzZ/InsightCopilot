import { ChevronDown, RefreshCcw, PlusCircle, MinusCircle, Bot } from 'lucide-react';
import { useUIStore } from '../store/useUIStore';
import styles from './Header.module.css';

function HeaderMetric({ label, value }: { label: string; value: string }) { 
  return (
    <div className={styles['header-metric']}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  ); 
}

export function Header() {
  const notify = useUIStore(state => state.notify);

  return (
    <header className={styles['app-header']}>
      <div className={styles['agent-info']}>
        <div className={styles['agent-avatar']}>林</div>
        <div className={styles['agent-details']}>
          <span className={styles['agent-id']}>d_*******34]</span>
          <div className={styles['agent-status-row']}>
            <div className={styles['status-badge']} onClick={() => notify('切换状态')}>
              <MinusCircle size={11} fill="currentColor" color="#fff" />
              <span>挂起</span>
              <ChevronDown size={11} />
            </div>
            <div className={styles['agent-actions']}>
              <button title="刷新" onClick={() => notify('已刷新')}><RefreshCcw size={13} /></button>
              <button title="新建" onClick={() => notify('新建会话')}><PlusCircle size={13} /></button>
            </div>
          </div>
        </div>
      </div>

      <div className={styles['header-metrics']}>
        <HeaderMetric label="今日接待" value="-" />
        <HeaderMetric label="未下单" value="-" />
        <HeaderMetric label="未付款" value="-" />
        <HeaderMetric label="已付款" value="-" />
        <HeaderMetric label="昨日旺旺满意度" value="-" />
        <HeaderMetric label="昨日3分钟响应率" value="-" />
        <HeaderMetric label="昨日平均响应时长" value="-" />
        <HeaderMetric label="询单转化率" value="-" />
      </div>

      <div className={styles['header-tools']}>
        <button className={styles['expand-btn']} onClick={() => notify('展开面板')}>
          <i className={styles['expand-icon']}><ChevronDown size={10} /></i>
          展开
        </button>
        <button className={styles['smart-btn']} onClick={() => notify('智能客服面板已打开')}>
          <Bot size={16} /> 智能客服
        </button>
      </div>
    </header>
  );
}
