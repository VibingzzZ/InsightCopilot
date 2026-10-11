import { Conversation } from '../types';
import styles from './Avatar.module.css';

export function Avatar({ text, risk }: { text: string; risk: Conversation['risk'] | 'normal' }) {
  const riskClass = risk !== 'normal' ? styles[risk] : '';
  return <div className={`${styles.avatar} ${riskClass}`}>{text}</div>;
}
