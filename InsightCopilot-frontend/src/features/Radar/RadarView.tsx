import { RotateCcw, Plus, Activity, Clock3, AlertTriangle, CheckCircle2, Filter } from 'lucide-react';
import { useUIStore } from '../../store/useUIStore';
import { useChatStore } from '../../store/useChatStore';
import { mockPromiseRows } from '../../data/mockData';
import { Metric } from '../../components/Metric';
import styles from './RadarView.module.css';

export function RadarView() {
  const promiseFilter = useUIStore(state => state.promiseFilter);
  const setPromiseFilter = useUIStore(state => state.setPromiseFilter);
  const scanDone = useUIStore(state => state.scanDone);
  const setScanDone = useUIStore(state => state.setScanDone);
  const setOverlay = useUIStore(state => state.setOverlay);
  const notify = useUIStore(state => state.notify);
  
  const customPromises = useChatStore(state => state.customPromises);

  const visiblePromises = [...mockPromiseRows, ...customPromises].filter(p => 
    promiseFilter === 'all' || (promiseFilter === 'done' ? p.status === 'done' : p.status !== 'done')
  );

  const handleScan = () => {
    setScanDone(true);
    notify('扫描完成：发现 1 条即将到期承诺');
  };

  return (
    <div className={styles['radar-view']}>
      <header className={styles['radar-heading']}>
        <div>
          <span>服务承诺跟踪</span>
          <h1>履约雷达</h1>
          <p>把聊天中的具体承诺转换为可验证任务</p>
        </div>
        <div>
          <button className={styles['outline-button']} onClick={handleScan}>
            <RotateCcw size={15} />
            {scanDone ? '再次扫描' : '模拟扫描'}
          </button>
          <button className={styles['primary-button']} onClick={() => setOverlay('new-tracking')}>
            <Plus size={15} />新建跟踪
          </button>
        </div>
      </header>
      
      <div className={styles['metric-grid']}>
        <Metric label="活跃承诺" value="18" detail="较昨日 +4" icon={Activity} />
        <Metric label="24小时内到期" value={scanDone ? '7' : '6'} detail="需要及时跟进" icon={Clock3} tone="warning" />
        <Metric label="已超时" value="3" detail="其中 2 条为退款" icon={AlertTriangle} tone="danger" />
        <Metric label="本周履约率" value="94.2%" detail="较上周 +2.8%" icon={CheckCircle2} tone="success" />
      </div>
      
      <section className={styles['promise-board']}>
        <div className={styles['board-header']}>
          <div>
            <h2>承诺队列</h2>
            <p>按风险等级和截止时间排序</p>
          </div>
          <div className={styles['filter-control']}>
            <Filter size={14} />
            <button className={promiseFilter === 'all' ? styles.active : ''} onClick={() => setPromiseFilter('all')}>全部 18</button>
            <button className={promiseFilter === 'attention' ? styles.active : ''} onClick={() => setPromiseFilter('attention')}>需关注 6</button>
            <button className={promiseFilter === 'done' ? styles.active : ''} onClick={() => setPromiseFilter('done')}>已履约 12</button>
          </div>
        </div>
        
        <div className={styles['promise-table']}>
          <div className={`${styles['promise-row']} ${styles.header}`}>
            <span>消费者</span>
            <span>承诺事项</span>
            <span>关联业务</span>
            <span>责任人</span>
            <span>截止时间</span>
            <span>状态</span>
          </div>
          {visiblePromises.map(row => (
            <div className={styles['promise-row']} key={`${row.customer}-${row.item}`}>
              <div className={styles['promise-customer']}>
                <span>{row.customer[0]}</span>
                <strong>{row.customer}</strong>
              </div>
              <div>
                <strong>{row.item}</strong>
                <small>客服已确认</small>
              </div>
              <span>{row.biz}</span>
              <span>{row.owner}</span>
              <strong className={styles[row.status]}>{row.deadline}</strong>
              <em className={styles[row.status]}>
                {row.status === 'urgent' ? '高风险' : row.status === 'due' ? '即将到期' : row.status === 'done' ? '已履约' : '进行中'}
              </em>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
