import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import ConnectionStatus from './ConnectionStatus';
import { SOCDataProvider, useSOCDataContext } from '../hooks/SOCDataContext';

function AppLayoutInner() {
  const { connectionStatus } = useSOCDataContext();

  return (
    <div className="app-layout">
      <div className="cyber-grid"></div>
      
      <Sidebar />

      <main className="main-content" style={{ overflowY: 'auto', height: '100vh' }}>
        <header className="top-navbar" style={{ 
          background: 'rgba(10, 15, 28, 0.8)',
          borderBottom: '1px solid var(--border-color)',
          transition: 'all 0.5s ease'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <h2 style={{ fontSize: '1.25rem', letterSpacing: '0.5px' }}>Global Telemetry Overview</h2>
          </div>
          <ConnectionStatus status={connectionStatus} />
        </header>

        {/* This Outlet will render Telemetry, Threats, Nodes, etc. based on the URL */}
        <Outlet />
      </main>
    </div>
  );
}

export default function AppLayout() {
  return (
    <SOCDataProvider>
      <AppLayoutInner />
    </SOCDataProvider>
  );
}
