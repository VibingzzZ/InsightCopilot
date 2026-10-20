import { useState } from 'react';
import { agentSocket } from '../services/socket';
import { api } from '../services/api';
import { useChatStore } from '../store/useChatStore';
import { useUIStore } from '../store/useUIStore';
import { ChevronDown, ChevronUp, Smartphone } from 'lucide-react';
import styles from './BuyerSimulator.module.css';

export function BuyerSimulator() {
  const [isOpen, setIsOpen] = useState(true);
  const [text, setText] = useState('');
  
  const selectedId = useChatStore(state => state.selectedId);
  const addMessage = useChatStore(state => state.addMessage);
  const notify = useUIStore(state => state.notify);

  const handleSend = async () => {
    if (!text.trim() || !selectedId) return;
    
    const messageContent = text.trim();
    setText('');

    // 1. 模拟买家消息加入到本地聊天流
    addMessage(selectedId, {
      role: 'buyer',
      text: messageContent,
      time: '刚刚'
    });
    
    // 2. 触发后端的 LangGraph 分析（后端设定了收到的 socket 就是买家的话）
    agentSocket.sendMessage(messageContent);
    
    notify('模拟买家发言成功，已触发后端分析');

    // 3. 异步持久化买家消息到数据库
    try {
      await api.sendSessionMessage(selectedId, {
        role: 'buyer',
        content: messageContent,
        sender_label: '消费者',
      });
    } catch (err) {
      console.error('Failed to persist buyer message:', err);
    }
  };

  return (
    <div className={`${styles.simulator} ${!isOpen ? styles.minimized : ''}`}>
      <div className={styles.header} onClick={() => setIsOpen(!isOpen)}>
        <span style={{display: 'flex', alignItems: 'center', gap: '6px'}}><Smartphone size={16} />模拟消费者手机端发言</span>
        {isOpen ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
      </div>
      <div className={styles.body}>
        <textarea 
          placeholder="输入消费者的测试发言，例如：你们这质量太差了，我要去工商局投诉！" 
          value={text} 
          onChange={e => setText(e.target.value)}
        />
        <div className={styles.footer}>
          <button onClick={handleSend} disabled={!text.trim()}>作为买家发送</button>
        </div>
      </div>
    </div>
  );
}
