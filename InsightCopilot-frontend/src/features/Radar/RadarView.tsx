import { useEffect, useMemo, useState } from 'react';
import { RotateCcw, Plus, Activity, Clock3, AlertTriangle, CheckCircle2, Filter } from 'lucide-react';
import { useUIStore } from '../../store/useUIStore';
import { useChatStore } from '../../store/useChatStore';
import { fetchPromises, scanPromises, type PromiseRow } from '../../services/promise';
import { Metric } from '../../components/Metric';
import styles from './RadarView.module.css';

interface DisplayRow {
  key: string;
  customer: string;
  item: string;
  biz: string;
  owner: string;
  deadline: string;
  statusClass: string;
  statusLabel: string;
}

const STATUS_META: Record<string, { cls: string; label: string }> = {
  pending_confirmation: { cls: '', label: '待确认' },
  active: { cls: '', label: '进行中' },
  due_soon: { cls: 'due', label: '即将到期' },
  overdue: { cls: 'urgent', label: '已超时' },
  fulfilled: { cls: 'done', label: '已履约' },
  changed: { cls: '', label: '已变更' },
  cancelled: { cls: '', label: '已取消' },
};

const OPEN_STATUSES = new Set(['pending_confirmation', 'active', 'due_soon', 'overdue']);

function fmtDeadline(due_at: string | null): string {
  if (!due_at) return '待确认时间';
  const m = due_at.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (m) return `${m[2]}-${m[3]} ${m[4]}:${m[5]}`;
  return due_at;
}

function toDisplayRow(p: PromiseRow): DisplayRow {
  const meta = STATUS_META[p.status] ?? { cls: '', label: p.status };
  const ownerLabel =
    p.owner_type === 'store' ? '门店' : p.owner_type === 'team' ? '专项团队' : p.owner_type === 'system' ? '系统' : '客服';
  return {
    key: p.promise_id,
    customer: p.customer_name_masked || '消费者',
    item: p.statement,
    biz: p.promise_type,
    owner: ownerLabel,
    deadline: fmtDeadline(p.due_at),
    statusClass: meta.cls,
    statusLabel: meta.label,
  };
}

export function RadarView() {
  const promiseFilter = useUIStore((state) => state.promiseFilter);
  const setPromiseFilter = useUIStore((state) => state.setPromiseFilter);
  const scanDone = useUIStore((state) => state.scanDone);
  const setScanDone = useUIStore((state) => state.setScanDone);
  const setOverlay = useUIStore((state) => state.setOverlay);
  const notify = useUIStore((state) => state.notify);

  const customPromises = useChatStore((state) => state.customPromises);

  const [promises, setPromises] = useState<PromiseRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await fetchPromises();
      setPromises(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // 扫描状态变化或过滤变化时重新拉取，保证雷达与后端一致
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scanDone]);

  const handleScan = async () => {
    try {
      await scanPromises();
    } catch (e) {
      notify(e instanceof Error ? e.message : '扫描失败');
    }
    setScanDone(true);
    await load();
    notify('扫描完成：已重算到期/超时状态');
  };

  // 本地「新建跟踪」的自定义承诺（mock 形态）也并入展示
  const customRows: DisplayRow[] = (customPromises as Array<DisplayRow & { status?: string }>).map((c, i) => ({
    key: `custom-${i}`,
    customer: c.customer,
    item: c.item,
    biz: c.biz,
    owner: c.owner,
    deadline: c.deadline,
    statusClass: c.status === 'urgent' ? 'urgent' : c.status === 'due' ? 'due' : c.status === 'done' ? 'done' : '',
    statusLabel:
      c.status === 'urgent' ? '高风险' : c.status === 'due' ? '即将到期' : c.status === 'done' ? '已履约' : '进行中',
  }));

  const realRows = useMemo(() => promises.map(toDisplayRow), [promises]);
  const allRows = [...realRows, ...customRows];

  const visibleRows = allRows.filter((r) => {
    if (promiseFilter === 'all') return true;
    if (promiseFilter === 'done') return r.statusLabel === '已履约';
    // 需关注：非终态
    return r.statusLabel !== '已履约' && r.statusLabel !== '已取消';
  });

  const metrics = useMemo(() => {
    const active = promises.filter((p) => OPEN_STATUSES.has(p.status)).length;
    const dueSoon = promises.filter((p) => p.status === 'due_soon' || p.status === 'overdue').length;
    const overdue = promises.filter((p) => p.status === 'overdue').length;
    const fulfilled = promises.filter((p) => p.status === 'fulfilled').length;
    const total = promises.length;
    const rate = total > 0 ? Math.round((fulfilled / total) * 1000) / 10 : 0;
    return { active, dueSoon, overdue, fulfilled, total, rate };
  }, [promises]);

  const attentionCount = metrics.active;

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

      {error && (
        <div style={{ color: '#c7524a', fontSize: 11, marginBottom: 10 }}>
          雷达数据加载失败：{error}（请确认后端已启动于 http://localhost:8000）
        </div>
      )}

      <div className={styles['metric-grid']}>
        <Metric label="活跃承诺" value={String(metrics.active)} detail={`共 ${metrics.total} 条`} icon={Activity} />
        <Metric
          label="24小时内到期"
          value={String(metrics.dueSoon)}
          detail="需要及时跟进"
          icon={Clock3}
          tone="warning"
        />
        <Metric label="已超时" value={String(metrics.overdue)} detail="其中多为退款类" icon={AlertTriangle} tone="danger" />
        <Metric label="履约率" value={`${metrics.rate}%`} detail={`已履约 ${metrics.fulfilled} 条`} icon={CheckCircle2} tone="success" />
      </div>

      <section className={styles['promise-board']}>
        <div className={styles['board-header']}>
          <div>
            <h2>承诺队列</h2>
            <p>按风险等级和截止时间排序</p>
          </div>
          <div className={styles['filter-control']}>
            <Filter size={14} />
            <button
              className={promiseFilter === 'all' ? styles.active : ''}
              onClick={() => setPromiseFilter('all')}
            >
              全部 {metrics.total}
            </button>
            <button
              className={promiseFilter === 'attention' ? styles.active : ''}
              onClick={() => setPromiseFilter('attention')}
            >
              需关注 {attentionCount}
            </button>
            <button
              className={promiseFilter === 'done' ? styles.active : ''}
              onClick={() => setPromiseFilter('done')}
            >
              已履约 {metrics.fulfilled}
            </button>
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
          {loading && <div style={{ padding: 18, color: '#8e97a4', fontSize: 11 }}>加载中…</div>}
          {!loading && visibleRows.length === 0 && (
            <div style={{ padding: 18, color: '#8e97a4', fontSize: 11 }}>
              暂无承诺。在会话中发送含承诺的客服消息后，系统会自动抽取并出现在此处。
            </div>
          )}
          {visibleRows.map((row) => (
            <div className={styles['promise-row']} key={row.key}>
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
              <strong className={row.statusClass ? styles[row.statusClass] : undefined}>{row.deadline}</strong>
              <em className={row.statusClass ? styles[row.statusClass] : undefined}>{row.statusLabel}</em>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
