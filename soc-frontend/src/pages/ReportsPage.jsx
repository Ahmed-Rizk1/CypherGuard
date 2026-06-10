/**
 * ReportsPage — Security reports overview.
 */
import { useState, useEffect } from 'react';
import { useAuth } from '../hooks/AuthContext';
import axios from 'axios';

export default function ReportsPage() {
  const { token } = useAuth();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await axios.get('/v1/api/dashboard/summary', { headers });
        setSummary(res.data?.data);
      } catch { /* ignore */ }
      setLoading(false);
    };
    fetchData();
  }, []);

  if (loading) {
    return <div className="page-content" style={{ textAlign: 'center', padding: '60px', color: '#6b7280' }}>Loading...</div>;
  }

  const severityColors = { critical: '#ef4444', high: '#f59e0b', medium: '#00d4ff', low: '#10b981' };

  return (
    <div className="page-content">
      <h1 style={{ color: '#fff', fontSize: '22px', marginBottom: '24px' }}>📊 Security Reports</h1>

      {/* Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '32px' }}>
        <div className="card" style={{ textAlign: 'center' }}>
          <div style={{ color: '#6b7280', fontSize: '12px', textTransform: 'uppercase', marginBottom: '8px' }}>Total Alerts</div>
          <div style={{ color: '#fff', fontSize: '36px', fontWeight: 700 }}>{summary?.total_alerts || 0}</div>
        </div>
        <div className="card" style={{ textAlign: 'center' }}>
          <div style={{ color: '#6b7280', fontSize: '12px', textTransform: 'uppercase', marginBottom: '8px' }}>Active Blocks</div>
          <div style={{ color: '#ef4444', fontSize: '36px', fontWeight: 700 }}>{summary?.active_blocked_ips || 0}</div>
        </div>
        <div className="card" style={{ textAlign: 'center' }}>
          <div style={{ color: '#6b7280', fontSize: '12px', textTransform: 'uppercase', marginBottom: '8px' }}>Packets/sec</div>
          <div style={{ color: '#00d4ff', fontSize: '36px', fontWeight: 700 }}>{summary?.live_metrics?.packets_per_sec || 0}</div>
        </div>
      </div>

      {/* Severity Breakdown */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <h3 style={{ color: '#fff', marginBottom: '16px' }}>Severity Breakdown</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '12px' }}>
          {Object.entries(summary?.severity_breakdown || {}).map(([sev, count]) => (
            <div key={sev} style={{
              background: `${severityColors[sev] || '#6b7280'}10`,
              border: `1px solid ${severityColors[sev] || '#6b7280'}30`,
              borderRadius: '8px',
              padding: '16px',
              textAlign: 'center',
            }}>
              <div style={{ color: severityColors[sev], fontSize: '24px', fontWeight: 700 }}>{count}</div>
              <div style={{ color: '#9ca3af', fontSize: '12px', textTransform: 'uppercase', marginTop: '4px' }}>{sev}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Status Breakdown */}
      <div className="card">
        <h3 style={{ color: '#fff', marginBottom: '16px' }}>Alert Status Distribution</h3>
        <div style={{ display: 'grid', gap: '8px' }}>
          {Object.entries(summary?.status_breakdown || {}).map(([status, count]) => {
            const total = summary?.total_alerts || 1;
            const pct = Math.round((count / total) * 100);
            return (
              <div key={status}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ color: '#9ca3af', fontSize: '13px', textTransform: 'capitalize' }}>{status.replace('_', ' ')}</span>
                  <span style={{ color: '#fff', fontSize: '13px' }}>{count} ({pct}%)</span>
                </div>
                <div style={{ height: '6px', background: '#1e2a3a', borderRadius: '3px', overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${pct}%`, background: '#00d4ff', borderRadius: '3px', transition: 'width 0.3s' }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
