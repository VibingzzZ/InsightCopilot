import { FileImage, ChevronRight } from 'lucide-react';
import { Message } from '../types';
import { Avatar } from './Avatar';
import styles from './MessageBubble.module.css';

export function MessageBubble({ message: m, customer, onOpenAttachment }: { message: Message; customer: string; onOpenAttachment: (name: string) => void }) {
  if (m.role === 'system') return <div className={styles['system-message']}>{m.text}</div>;
  
  return (
    <div className={`${styles.message} ${m.role === 'agent' ? styles.agent : ''}`}>
      <Avatar text={m.role === 'buyer' ? customer[0] : '客'} risk="normal" />
      <div>
        <div className={styles['message-meta']}>
          <strong>{m.role === 'buyer' ? customer : '客服林林'}</strong>
          <time>{m.time}</time>
        </div>
        <div className={styles.bubble}>
          {m.text}
          {m.attachment && (
            <div className={styles.attachment}>
              <div>
                <FileImage size={19} />
                <span>JPG</span>
              </div>
              <section>
                <strong>{m.attachment}</strong>
                <small>视觉模型识别中</small>
              </section>
              <button title="查看资料" onClick={() => onOpenAttachment(m.attachment!)}>
                <ChevronRight size={15} />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
