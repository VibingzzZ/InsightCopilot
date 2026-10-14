import { FileImage, ChevronRight, Download } from 'lucide-react';
import { Message } from '../types';
import { Avatar } from './Avatar';
import styles from './MessageBubble.module.css';

function fileExt(name?: string): string {
  if (!name) return 'FILE';
  const i = name.lastIndexOf('.');
  return i >= 0 ? name.slice(i + 1).toUpperCase().slice(0, 5) : 'FILE';
}

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
          {m.attachmentUrl && m.attachmentKind === 'image' && (
            <div className={styles['image-block']}>
              <img src={m.attachmentUrl} alt={m.attachment || '图片'} onClick={() => onOpenAttachment(m.attachmentUrl!)} />
            </div>
          )}
          {m.attachmentUrl && m.attachmentKind === 'attachment' && (
            <div className={styles.attachment}>
              <div>
                <FileImage size={19} />
                <span>{fileExt(m.attachment)}</span>
              </div>
              <section>
                <strong>{m.attachment}</strong>
                <small>点击查看或下载</small>
              </section>
              <a href={m.attachmentUrl} download title="下载" onClick={(e) => e.stopPropagation()}>
                <Download size={15} />
              </a>
              <button title="查看资料" onClick={() => onOpenAttachment(m.attachmentUrl!)}>
                <ChevronRight size={15} />
              </button>
            </div>
          )}
          {!m.attachmentUrl && m.attachment && (
            <div className={styles.attachment}>
              <div>
                <FileImage size={19} />
                <span>{fileExt(m.attachment)}</span>
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
