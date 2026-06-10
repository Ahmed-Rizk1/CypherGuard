import { AlertTriangle, ShieldBan } from 'lucide-react';
import { useSOCDataContext } from '../hooks/SOCDataContext';

export default function LiveAlertsWidget() {
  const { alerts, blockedIps } = useSOCDataContext();

  return (
    <div className="glass-panel" style={{ padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div style={{ 
        background: 'var(--accent-red)', 
        padding: '0.5rem 1rem', 
        borderBottom: '1px solid var(--border-color)',
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        color: '#000',
        fontSize: '0.8rem',
        fontWeight: '800',
        textTransform: 'uppercase'
      }}>
        <AlertTriangle size={16} /> LIVE THREAT FEED
      </div>
      
      <div style={{
        background: 'rgba(0,0,0,0.4)',
        padding: '1rem',
        height: '250px',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem'
      }}>
        {alerts.length === 0 && blockedIps.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', marginTop: '2rem' }}>
            No live activity detected.
          </div>
        ) : (
          <>
            {alerts.slice(0, 15).map((a, i) => (
              <div key={`alert-${i}`} className="animate-slide-in" style={{ 
                display: 'flex', 
                flexDirection: 'column', 
                gap: '0.2rem',
                borderLeft: '2px solid var(--accent-red)',
                paddingLeft: '0.5rem',
                animationDelay: `${i * 0.05}s`
              }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                  [{a.severity.toUpperCase()}] {a.attack_type}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                  Source: {a.src_ip} {a.country ? `(${a.country})` : ''}
                </span>
              </div>
            ))}
            {blockedIps.slice(0, 5).map((ip, i) => (
              <div key={`block-${i}`} className="animate-slide-in" style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '0.5rem', 
                color: 'var(--text-muted)',
                fontSize: '0.75rem',
                padding: '0.25rem 0',
                borderBottom: '1px solid rgba(255,255,255,0.05)'
              }}>
                <ShieldBan size={12} /> {ip} was blocked by firewall
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
