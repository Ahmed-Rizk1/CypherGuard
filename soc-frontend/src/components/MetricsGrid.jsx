import { Activity, Zap, Server, ShieldX } from 'lucide-react';

export default function MetricsGrid({ metrics, blockedCount }) {
  const cards = [
    {
      title: 'Active Connections',
      value: metrics.active_connections,
      icon: <Server size={24} />,
      colorVar: '--accent-cyan'
    },
    {
      title: 'Traffic (Pkt/s)',
      value: metrics.packets_per_sec,
      icon: <Activity size={24} />,
      colorVar: '--accent-purple'
    },
    {
      title: 'Bandwidth (B/s)',
      value: metrics.bytes_per_sec,
      icon: <Zap size={24} />,
      colorVar: '--accent-orange'
    },
    {
      title: 'Active IP Blocks',
      value: blockedCount,
      icon: <ShieldX size={24} />,
      colorVar: '--accent-red'
    }
  ];

  return (
    <div className="metrics-grid">
      {cards.map((c, i) => (
        <div 
          key={i} 
          className="glass-panel" 
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '1.25rem', 
            padding: '1.5rem',
            transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
            cursor: 'default'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-5px)';
            e.currentTarget.style.boxShadow = `0 15px 30px -10px color-mix(in srgb, var(${c.colorVar}) 30%, transparent), inset 0 1px 0 rgba(255, 255, 255, 0.1)`;
            e.currentTarget.style.borderColor = `var(${c.colorVar})`;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = '0 10px 40px -10px rgba(0, 0, 0, 0.5)';
            e.currentTarget.style.borderColor = 'var(--border-color)';
          }}
        >
          <div style={{
            padding: '12px',
            borderRadius: '12px',
            background: `color-mix(in srgb, var(${c.colorVar}) 15%, transparent)`,
            color: `var(${c.colorVar})`,
            display: 'flex',
            boxShadow: `inset 0 0 0 1px color-mix(in srgb, var(${c.colorVar}) 30%, transparent)`
          }}>
            {c.icon}
          </div>
          <div>
            <p style={{ 
              margin: '0 0 0.25rem 0', 
              fontSize: '0.8rem', 
              color: 'var(--text-secondary)',
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
              fontWeight: '600'
            }}>
              {c.title}
            </p>
            <h2 style={{ 
              margin: 0, 
              fontSize: '2rem', 
              fontWeight: '700',
              textShadow: `0 0 20px color-mix(in srgb, var(${c.colorVar}) 40%, transparent)`,
              fontFamily: 'var(--font-mono)'
            }}>
              {c.value.toLocaleString()}
            </h2>
          </div>
        </div>
      ))}
    </div>
  );
}
