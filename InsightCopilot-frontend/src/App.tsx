import { Routes, Route, Navigate } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { Workspace } from './features/Workspace/Workspace';
import { RadarView } from './features/Radar/RadarView';
import { Overlay } from './components/Overlay';
import { BuyerSimulator } from './components/BuyerSimulator';
import { useUIStore } from './store/useUIStore';
import { useChatStore } from './store/useChatStore';
import { mockConversations } from './data/mockData';
import { CheckCircle2 } from 'lucide-react';
import styles from './App.module.css';

function App() {
  const overlay = useUIStore(state => state.overlay);
  const setOverlay = useUIStore(state => state.setOverlay);
  const toast = useUIStore(state => state.toast);
  const selectedAttachment = useUIStore(state => state.selectedAttachment);
  
  const selectedId = useChatStore(state => state.selectedId);
  const addCustomPromise = useChatStore(state => state.addCustomPromise);
  
  const selected = mockConversations.find(c => c.id === selectedId) ?? mockConversations[0];

  return (
    <div className={styles['content-box']}>
      <div className={styles['customer-service-wrap']}>
        <Sidebar />
        <main className={styles['app-main']}>
          <Header />
          <Routes>
            <Route path="/" element={<Navigate to="/workspace" replace />} />
            <Route path="/workspace" element={<Workspace />} />
            <Route path="/radar" element={<RadarView />} />
          </Routes>
        </main>
        
        <div className={`${styles.toast} ${toast ? styles.show : ''}`}>
          <CheckCircle2 size={16} />
          <span>{toast}</span>
        </div>
        
        {overlay !== 'none' && (
          <Overlay 
            type={overlay} 
            conversation={selected} 
            attachment={selectedAttachment} 
            onClose={() => setOverlay('none')} 
            onCreate={(row) => {
              addCustomPromise(row);
              setOverlay('none');
              useUIStore.getState().notify('已加入履约跟踪');
            }} 
          />
        )}
        
        {/* 开发与测试专用的消费者模拟器 */}
        <BuyerSimulator />
      </div>
    </div>
  );
}

export default App;
