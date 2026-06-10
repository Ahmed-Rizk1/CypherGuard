import { AlertTriangle, Clock, Target, Zap, Info, ShieldCheck } from 'lucide-react';

export default function ThreatLog({ alerts }) {
  const getSeverityColor = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'critical': return 'var(--accent-red)';
      case 'high': return 'var(--accent-orange)';
      case 'medium': return 'var(--accent-cyan)';
      case 'low': return 'var(--accent-green)';
      default: return 'var(--text-secondary)';
    }
  };

  const getSeverityBg = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'critical': return 'var(--accent-red-dim)';
      case 'high': return 'var(--accent-orange-dim)';
      case 'medium': return 'var(--accent-cyan-dim)';
      case 'low': return 'var(--accent-green-dim)';
      default: return 'rgba(255,255,255,0.05)';
    }
  };

  const getCountryFlag = (code) => {
    if (!code) return <span style={{ marginRight: '6px' }}>🌍</span>;
    return (
      <img 
        src={`https://flagcdn.com/w20/${code.toLowerCase()}.png`} 
        srcSet={`https://flagcdn.com/w40/${code.toLowerCase()}.png 2x`}
        alt={code}
        style={{ width: '16px', height: '12px', marginRight: '4px', borderRadius: '2px', objectFit: 'cover', display: 'inline-block', verticalAlign: 'middle' }}
      />
    );
  };

  return (
    <div className="glass-panel" style={{ maxHeight: '600px', overflowY: 'auto' }}>
      <div className="panel-header" style={{ position: 'sticky', top: '-1.5rem', background: 'rgba(17,24,39,0.9)', padding: '1.5rem 0 1rem', margin: '-1.5rem 0 1rem', zIndex: 10, backdropFilter: 'blur(8px)' }}>
        <h3 className="panel-title">
          <AlertTriangle size={20} color="var(--accent-orange)" />
          AI Threat Analysis Stream
        </h3>
      </div>

      {alerts.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-muted)' }}>
          <ShieldCheck size={48} style={{ opacity: 0.2, margin: '0 auto 1rem' }} />
          <p>No active threats detected in the current window.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {alerts.map((alert, i) => (
            <div 
              key={i} 
              className="animate-slide-in"
              style={{
                background: 'rgba(0,0,0,0.2)',
                border: '1px solid var(--border-color)',
                borderLeft: `3px solid ${getSeverityColor(alert.severity)}`,
                borderRadius: '8px',
                padding: '1.25rem',
                animationDelay: `${i * 0.05}s`
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem', fontSize: '0.85rem' }}>
                <span style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Clock size={14} />
                  {new Date(alert.timestamp).toLocaleTimeString()}
                </span>
                <span style={{ 
                  background: 'var(--accent-purple-dim)', 
                  color: 'var(--accent-purple)', 
                  padding: '0.2rem 0.6rem', 
                  borderRadius: '4px',
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  letterSpacing: '0.5px'
                }}>
                  {alert._source?.toUpperCase() || 'ML MODEL'}
                </span>
              </div>

              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                <span style={{ 
                  background: getSeverityBg(alert.severity), 
                  color: getSeverityColor(alert.severity),
                  padding: '0.3rem 0.6rem',
                  borderRadius: '4px',
                  fontSize: '0.75rem',
                  fontWeight: '700',
                  textTransform: 'uppercase'
                }}>
                  {alert.severity}
                </span>
                <span style={{ 
                  background: 'rgba(255,255,255,0.05)', 
                  color: 'var(--text-primary)',
                  padding: '0.3rem 0.6rem',
                  borderRadius: '4px',
                  fontSize: '0.75rem',
                  fontWeight: '600'
                }}>
                  {alert.attack_type}
                </span>
                <span style={{ 
                  background: 'rgba(59, 130, 246, 0.15)', 
                  color: '#60A5FA',
                  padding: '0.3rem 0.6rem',
                  borderRadius: '4px',
                  fontSize: '0.75rem',
                  fontFamily: 'var(--font-mono)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.3rem'
                }}>
                  <Target size={12} />
                  <span style={{ fontSize: '1rem', marginRight: '4px' }}>{getCountryFlag(alert.country)}</span>
                  {alert.src_ip}
                </span>
              </div>

              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: '1.5', margin: '0 0 1rem 0' }}>
                {alert.explanation}
              </p>

              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '0.5rem', 
                color: 'var(--accent-orange)', 
                fontSize: '0.85rem',
                fontWeight: '500',
                background: 'rgba(245, 158, 11, 0.05)',
                padding: '0.5rem 0.75rem',
                borderRadius: '6px'
              }}>
                <Zap size={14} />
                {alert.recommendation}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
