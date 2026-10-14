import { useState } from 'react';
import { FileImage, CheckCircle2, X, Plus } from 'lucide-react';
import { Conversation, PromiseRow } from '../types';
import styles from './Overlay.module.css';

interface OverlayProps {
  type: 'order' | 'attachment' | 'new-tracking' | 'module';
  conversation: Conversation;
  attachment: string;
  onClose: () => void;
  onCreate: (row: PromiseRow) => void;
}

export function Overlay({ type, conversation, attachment, onClose, onCreate }: OverlayProps) {
  const [item, setItem] = useState('跟进消费者服务承诺');
  const [deadline, setDeadline] = useState('今天 18:00');
  const [owner, setOwner] = useState('客服林林');
  
  const title = type === 'order' ? '订单详情' : type === 'attachment' ? '资料预览' : type === 'new-tracking' ? '新建履约跟踪' : '模块预览';
  
  const submit = () => onCreate({ 
    customer: conversation.customer, 
    item, 
    biz: `客服跟进 · ${conversation.id}`, 
    deadline, 
    status: 'active', 
    owner 
  });

  return (
    <div className={styles['overlay-backdrop']} role="presentation" onClick={onClose}>
      <section className={styles['overlay-panel']} role="dialog" aria-modal="true" aria-label={title} onClick={e => e.stopPropagation()}>
        <header>
          <div>
            <span>知微客服副驾</span>
            <h2>{title}</h2>
          </div>
          <button title="关闭" onClick={onClose}><X size={17} /></button>
        </header>
        
        {type === 'order' && (
          <div className={styles['overlay-content']}>
            <dl className={styles['overlay-facts']}>
              <div><dt>消费者</dt><dd>{conversation.customer}</dd></div>
              <div><dt>会话</dt><dd>{conversation.id}</dd></div>
              <div><dt>订单号</dt><dd>{conversation.order}</dd></div>
              <div><dt>关联工单</dt><dd>{conversation.ticket}</dd></div>
              <div><dt>场景</dt><dd>{conversation.scene}</dd></div>
            </dl>
            <p className={styles['overlay-note']}>订单和工单数据来自官方业务数据静态快照。</p>
          </div>
        )}
        
        {type === 'attachment' && (
          <div className={styles['overlay-content']}>
            {(() => {
              const isMediaUrl = !!attachment && (attachment.startsWith('/media/') || attachment.startsWith('http'));
              const isImage = !!attachment && /\.(png|jpe?g|gif|webp|bmp)(\?.*)?$/i.test(attachment);
              if (isMediaUrl && isImage) {
                return (
                  <div className={styles['attachment-image-wrap']}>
                    <img src={attachment} alt="资料预览" />
                  </div>
                );
              }
              if (isMediaUrl) {
                return (
                  <div className={styles['attachment-preview']}>
                    <FileImage size={32} />
                    <strong>{decodeURIComponent(attachment.split('/').pop() || attachment)}</strong>
                    <a href={attachment} target="_blank" rel="noreferrer" download>下载 / 打开</a>
                  </div>
                );
              }
              return (
                <div className={styles['attachment-preview']}>
                  <FileImage size={32} />
                  <strong>{attachment || '会话附件'}</strong>
                  <span>已完成类型识别，等待人工确认内容</span>
                </div>
              );
            })()}
            <p className={styles['overlay-note']}>资料经后端 /api/uploads 上传，此处展示脱敏预览（演示环境不做原始内容解析）。</p>
          </div>
        )}
        
        {type === 'module' && (
          <div className={styles['overlay-content']}>
            <div className={styles['module-placeholder']}>
              <CheckCircle2 size={24} />
              <strong>本地演示模块</strong>
              <span>该模块的页面和接口将在后续后端接入阶段启用。</span>
            </div>
          </div>
        )}
        
        {type === 'new-tracking' && (
          <form className={styles['tracking-form']} onSubmit={e => { e.preventDefault(); submit(); }}>
            <label>
              承诺事项
              <input value={item} onChange={e => setItem(e.target.value)} required />
            </label>
            <label>
              截止时间
              <input value={deadline} onChange={e => setDeadline(e.target.value)} required />
            </label>
            <label>
              责任人
              <input value={owner} onChange={e => setOwner(e.target.value)} required />
            </label>
            <p>将为 {conversation.customer} 创建本地跟踪记录。</p>
            <footer>
              <button type="button" className={styles['outline-button']} onClick={onClose}>取消</button>
              <button type="submit" className={styles['primary-button']}><Plus size={14} />创建跟踪</button>
            </footer>
          </form>
        )}
      </section>
    </div>
  );
}
