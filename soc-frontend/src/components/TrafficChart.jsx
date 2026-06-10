import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Activity, Zap } from 'lucide-react';

export default function TrafficChart({ data, dataKey, title, color, gradientId, yFormatter, icon }) {
  
  // Custom styled tooltip
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div style={{
          background: 'rgba(10, 15, 28, 0.9)',
          border: `1px solid ${color}`,
          padding: '0.75rem 1rem',
          borderRadius: '8px',
          boxShadow: `0 0 20px color-mix(in srgb, ${color} 30%, transparent), inset 0 0 10px color-mix(in srgb, ${color} 10%, transparent)`,
          backdropFilter: 'blur(10px)'
        }}>
          <p style={{ margin: '0 0 0.5rem 0', color: 'var(--text-secondary)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '1px' }}>{label}</p>
          <p style={{ margin: 0, color: '#fff', fontWeight: '700', fontSize: '1.2rem', fontFamily: 'var(--font-mono)', textShadow: `0 0 10px ${color}` }}>
            {yFormatter ? yFormatter(payload[0].value) : payload[0].value}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="glass-panel">
      <div className="panel-header">
        <h3 className="panel-title">
          {icon === 'Activity' && <Activity size={18} color={color} />}
          {icon === 'Zap' && <Zap size={18} color={color} />}
          {title}
        </h3>
      </div>
      
      <div style={{ width: '100%', height: 250 }}>
        <ResponsiveContainer>
          <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.4}/>
                <stop offset="95%" stopColor={color} stopOpacity={0.0}/>
              </linearGradient>
            </defs>
            <XAxis 
              dataKey="time" 
              stroke="var(--text-muted)" 
              fontSize={11}
              tickLine={false}
              axisLine={false}
              minTickGap={20}
            />
            <YAxis 
              stroke="var(--text-muted)" 
              fontSize={11}
              tickLine={false}
              axisLine={false}
              tickFormatter={yFormatter}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area 
              type="monotone" 
              dataKey={dataKey} 
              stroke={color} 
              strokeWidth={2}
              fillOpacity={1} 
              fill={`url(#${gradientId})`} 
              isAnimationActive={false} // Disable to avoid jitter on fast updates
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
