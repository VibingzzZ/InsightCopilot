import { Bell, ChevronDown } from 'lucide-react';
import { useUIStore } from '../store/useUIStore';
import styles from './Header.module.css';

function HeaderMetric({ label, value }: { label: string; value: string }) { 
  return (
    <div className={styles['header-metric']}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  ); 
}

export function Header() {
  const notify = useUIStore(state => state.notify);

  return (
    <header className={styles['app-header']}>
      <div className={styles['header-brand']}>
        <strong>知微客服副驾</strong>
        <span>人工客服服务工作台</span>
      </div>
      <div className={styles['header-metrics']}>
        <HeaderMetric label="今日接待" value="36" />
        <HeaderMetric label="待跟进" value="5" />
        <HeaderMetric label="3分钟响应率" value="96.8%" />
        <HeaderMetric label="履约率" value="94.2%" />
      </div>
      <div className={styles['header-tools']}>
        <span className={styles['sync']}><i />数据已同步</span>
        <button title="通知" onClick={() => notify('暂无新的服务提醒')}>
          <Bell size={18} />
          <b />
        </button>
        <button className={styles['agent-profile']} title="当前账号" onClick={() => notify('当前账号：客服林林')}>
          <span>客服林林</span>
          <ChevronDown size={15} />
        </button>
      </div>
    </header>
  );
}
