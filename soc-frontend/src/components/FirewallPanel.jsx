import { ShieldBan, Lock, CheckCircle2 } from 'lucide-react';

export default function FirewallPanel({ blockedIps }) {
  return (
    <div className="glass-panel" style={{ maxHeight: '600px', overflowY: 'auto' }}>
      <div className="panel-header" style={{ position: 'sticky', top: '-1.5rem', background: 'rgba(17,24,39,0.9)', padding: '1.5rem 0 1rem', margin: '-1.5rem 0 1rem', zIndex: 10, backdropFilter: 'blur(8px)' }}>
        <h3 className="panel-title">
          <ShieldBan size={20} color="var(--accent-red)" />
          Active Defense / Blocklist
        </h3>
      </div>

      {blockedIps.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-muted)' }}>
          <CheckCircle2 size={48} style={{ opacity: 0.2, margin: '0 auto 1rem' }} color="var(--accent-green)" />
          <p>No malicious IPs are currently blocked.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '0.75rem' }}>
          {blockedIps.map((ip, i) => (
            <div 
              key={i} 
              className="animate-slide-in"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.75rem',
                background: 'var(--accent-red-dim)',
                border: '1px solid rgba(255, 42, 84, 0.3)',
                borderRadius: '6px',
                color: '#fca5a5',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.85rem',
                boxShadow: 'inset 0 0 10px rgba(255, 42, 84, 0.1)',
                animationDelay: `${i * 0.05}s`
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Lock size={14} color="var(--accent-red)" />
                {ip}
              </div>
              <button 
                onClick={() => {
                  fetch(`/api/firewall/blocklist/${ip}`, { method: 'DELETE' })
                    .then(res => res.json())
                    .then(data => {
                      if (data.status === 'success') {
                        // The socket stream will naturally update the blocklist next cycle,
                        // but you could add local state optimistic updates if needed.
                        console.log(`Unblocked ${ip}`);
                      }
                    });
                }}
                title="Unblock IP"
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '4px',
                  borderRadius: '4px',
                  transition: 'all 0.2s ease'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = 'var(--accent-green)';
                  e.currentTarget.style.background = 'rgba(16, 185, 129, 0.2)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = 'var(--text-secondary)';
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                <ShieldBan size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
