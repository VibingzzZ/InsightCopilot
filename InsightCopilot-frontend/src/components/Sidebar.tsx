import { LayoutDashboard, MessageCircle, Activity, ClipboardCheck, Users, Bot } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useUIStore } from '../store/useUIStore';
import styles from './Sidebar.module.css';

function NavButton({ label, icon: Icon, to, badge, onClick }: { label: string; icon: any; to?: string; badge?: string; onClick?: () => void }) {
  if (to) {
    return (
      <NavLink to={to} className={({ isActive }) => isActive ? styles.active : ''} title={label} onClick={onClick}>
        <Icon size={20} /><span>{label}</span>{badge && <b>{badge}</b>}
      </NavLink>
    );
  }
  return (
    <button onClick={onClick} title={label}>
      <Icon size={20} /><span>{label}</span>{badge && <b>{badge}</b>}
    </button>
  );
}

export function Sidebar() {
  const setOverlay = useUIStore(state => state.setOverlay);
  const notify = useUIStore(state => state.notify);

  return (
    <aside className={styles.globalNav}>
      <div className={styles.brand} aria-label="知微">知</div>
      <nav>
        <NavButton to="/workspace" label="工作台" icon={LayoutDashboard} />
        <NavButton label="消息" icon={MessageCircle} badge="12" onClick={() => notify('暂无新消息')} />
        <NavButton to="/radar" label="履约" icon={Activity} badge="3" />
        <NavButton label="工单" icon={ClipboardCheck} onClick={() => { setOverlay('module'); notify('工单模块已切换到本地演示'); }} />
        <NavButton label="客户" icon={Users} onClick={() => { setOverlay('module'); notify('客户模块已切换到本地演示'); }} />
      </nav>
      <div className={styles.navBottom}>
        <button title="服务设置"><Bot size={20} /></button>
        <div className={styles.navAvatar}>林</div>
      </div>
    </aside>
  );
}
