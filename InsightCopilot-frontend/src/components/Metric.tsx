import styles from './Metric.module.css';

export function Metric({ label, value, detail, icon: Icon, tone = '' }: { label: string; value: string; detail: string; icon: any; tone?: string }) { 
  const toneClass = tone ? styles[tone] : '';
  return (
    <div className={`${styles.metric} ${toneClass}`}>
      <div>
        <span>{label}</span>
        <Icon size={17} />
      </div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  ); 
}
