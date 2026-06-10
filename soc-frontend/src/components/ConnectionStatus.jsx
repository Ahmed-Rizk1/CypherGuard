import { ShieldAlert, ShieldCheck, RefreshCw } from 'lucide-react';

export default function ConnectionStatus({ status }) {
  const isConnected = status === 'connected';

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '0.5rem',
      padding: '0.4rem 0.75rem',
      borderRadius: '999px',
      background: isConnected ? 'var(--accent-green-dim)' : 'var(--accent-orange-dim)',
      border: `1px solid ${isConnected ? 'var(--accent-green)' : 'var(--accent-orange)'}`,
      color: isConnected ? 'var(--accent-green)' : 'var(--accent-orange)',
      fontSize: '0.85rem',
      fontWeight: '600',
      letterSpacing: '0.5px'
    }}>
      {isConnected ? (
        <>
          <span className="animate-pulse-glow" style={{ display: 'flex' }}>
            <ShieldCheck size={16} />
          </span>
          SECURE LINK ACTIVE
        </>
      ) : (
        <>
          <RefreshCw size={16} className="animate-spin" style={{ animation: 'spin 2s linear infinite' }} />
          RECONNECTING...
        </>
      )}
    </div>
  );
}
