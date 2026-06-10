import { useState } from 'react';
import { Search, Filter, ShieldAlert, Download } from 'lucide-react';
import { useSOCDataContext } from '../hooks/SOCDataContext';
import ThreatModal from '../components/ThreatModal';

const getCountryFlag = (code) => {
  if (!code) return <span style={{ marginRight: '6px' }}>🌍</span>;
  return (
    <img 
      src={`https://flagcdn.com/w20/${code.toLowerCase()}.png`} 
      srcSet={`https://flagcdn.com/w40/${code.toLowerCase()}.png 2x`}
      alt={code}
      style={{ width: '20px', height: '15px', marginRight: '8px', borderRadius: '2px', objectFit: 'cover', display: 'inline-block', verticalAlign: 'middle' }}
    />
  );
};

export default function Threats() {
  const { alerts } = useSOCDataContext();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedAlert, setSelectedAlert] = useState(null);

  const filteredAlerts = alerts.filter(a => 
    a.src_ip.includes(searchTerm) || 
    a.attack_type.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Sanitize a CSV cell value to prevent formula injection in spreadsheet apps
  const sanitizeCSV = (val) => {
    const str = String(val ?? '');
    // Prefix dangerous characters that could trigger formula execution in Excel
    if (/^[=+\-@\t\r]/.test(str)) return `'${str}`;
    // Wrap in quotes if contains comma, quote, or newline
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const handleExportCSV = () => {
    if (filteredAlerts.length === 0) return;
    
    const headers = ['Time', 'Source IP', 'Country', 'Attack Type', 'Severity', 'Confidence'];
    const rows = filteredAlerts.map(a => [
      sanitizeCSV(new Date(a.timestamp).toISOString()),
      sanitizeCSV(a.src_ip),
      sanitizeCSV(a.country || 'Unknown'),
      sanitizeCSV(a.attack_type),
      sanitizeCSV(a.severity),
      sanitizeCSV((a.confidence * 100).toFixed(1) + '%')
    ]);
    
    const csvContent = "data:text/csv;charset=utf-8," 
      + headers.join(",") + "\n" 
      + rows.map(e => e.join(",")).join("\n");
      
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `threat_intelligence_${new Date().getTime()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="dashboard-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>Threat Intelligence</h1>
          <p style={{ color: 'var(--text-secondary)' }}>Detailed record of all malicious activity detected by the AI engine.</p>
        </div>

        <div style={{ display: 'flex', gap: '1rem' }}>
          <div style={{ position: 'relative' }}>
            <Search size={18} color="var(--text-muted)" style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)' }} />
            <input 
              type="text" 
              placeholder="Search IP or Attack Type..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                background: 'rgba(10, 15, 28, 0.8)',
                border: '1px solid var(--border-highlight)',
                color: 'white',
                padding: '0.75rem 1rem 0.75rem 2.5rem',
                borderRadius: '8px',
                width: '320px',
                outline: 'none',
                transition: 'all 0.3s ease',
                boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.2)'
              }}
              onFocus={(e) => {
                e.target.style.borderColor = 'var(--accent-cyan)';
                e.target.style.boxShadow = '0 0 15px var(--accent-cyan-dim), inset 0 2px 4px rgba(0,0,0,0.2)';
              }}
              onBlur={(e) => {
                e.target.style.borderColor = 'var(--border-highlight)';
                e.target.style.boxShadow = 'inset 0 2px 4px rgba(0,0,0,0.2)';
              }}
            />
          </div>
          <button 
            onClick={handleExportCSV}
            style={{
            background: 'var(--accent-cyan-dim)',
            border: '1px solid var(--accent-cyan)',
            color: 'var(--accent-cyan)',
            padding: '0.75rem 1rem',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            cursor: 'pointer',
            transition: 'all 0.3s ease',
            fontWeight: '600'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--accent-cyan)';
            e.currentTarget.style.color = '#000';
            e.currentTarget.style.boxShadow = '0 0 15px var(--accent-cyan-glow)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'var(--accent-cyan-dim)';
            e.currentTarget.style.color = 'var(--accent-cyan)';
            e.currentTarget.style.boxShadow = 'none';
          }}>
            <Download size={18} /> Export CSV
          </button>

          <button style={{
            background: 'rgba(10, 15, 28, 0.8)',
            border: '1px solid var(--border-highlight)',
            color: 'white',
            padding: '0.75rem 1rem',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            cursor: 'pointer',
            transition: 'all 0.3s ease'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--accent-purple)';
            e.currentTarget.style.color = 'var(--accent-purple)';
            e.currentTarget.style.boxShadow = '0 0 15px var(--accent-purple-dim)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--border-highlight)';
            e.currentTarget.style.color = 'white';
            e.currentTarget.style.boxShadow = 'none';
          }}>
            <Filter size={18} /> Filter
          </button>
        </div>
      </div>

      <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ background: 'rgba(0,0,0,0.3)', borderBottom: '1px solid var(--border-color)' }}>
              <th style={{ padding: '1.25rem', color: 'var(--text-secondary)', fontWeight: '600', fontSize: '0.85rem', textTransform: 'uppercase' }}>Time</th>
              <th style={{ padding: '1.25rem', color: 'var(--text-secondary)', fontWeight: '600', fontSize: '0.85rem', textTransform: 'uppercase' }}>Source IP</th>
              <th style={{ padding: '1.25rem', color: 'var(--text-secondary)', fontWeight: '600', fontSize: '0.85rem', textTransform: 'uppercase' }}>Attack Type</th>
              <th style={{ padding: '1.25rem', color: 'var(--text-secondary)', fontWeight: '600', fontSize: '0.85rem', textTransform: 'uppercase' }}>Severity</th>
              <th style={{ padding: '1.25rem', color: 'var(--text-secondary)', fontWeight: '600', fontSize: '0.85rem', textTransform: 'uppercase' }}>Confidence</th>
              <th style={{ padding: '1.25rem', color: 'var(--text-secondary)', fontWeight: '600', fontSize: '0.85rem', textTransform: 'uppercase' }}>Action Taken</th>
            </tr>
          </thead>
          <tbody>
            {filteredAlerts.length === 0 ? (
              <tr>
                <td colSpan="6" style={{ padding: '4rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <ShieldAlert size={48} style={{ opacity: 0.2, margin: '0 auto 1rem' }} />
                  <p>No threats match your search criteria.</p>
                </td>
              </tr>
            ) : (
              filteredAlerts.map((alert, i) => (
                <tr 
                  key={i} 
                  onClick={() => setSelectedAlert(alert)}
                  style={{ 
                    borderBottom: '1px solid rgba(255,255,255,0.02)', 
                    transition: 'all 0.2s ease',
                    cursor: 'pointer'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
                    e.currentTarget.style.transform = 'scale(1.01)';
                    e.currentTarget.style.boxShadow = '0 4px 15px rgba(0,0,0,0.2)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent';
                    e.currentTarget.style.transform = 'scale(1)';
                    e.currentTarget.style.boxShadow = 'none';
                  }}
                >
                  <td style={{ padding: '1.25rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                    {new Date(alert.timestamp).toLocaleTimeString()}
                  </td>
                  <td style={{ padding: '1.25rem', fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>
                    <span style={{ fontSize: '1rem', marginRight: '6px' }}>{getCountryFlag(alert.country)}</span>
                    {alert.src_ip}
                  </td>
                  <td style={{ padding: '1.25rem', fontWeight: '500', color: 'var(--text-primary)' }}>
                    {alert.attack_type}
                  </td>
                  <td style={{ padding: '1.25rem' }}>
                    <span style={{
                      background: alert.severity === 'critical' ? 'var(--accent-red-dim)' : 'var(--accent-orange-dim)',
                      color: alert.severity === 'critical' ? 'var(--accent-red)' : 'var(--accent-orange)',
                      border: `1px solid ${alert.severity === 'critical' ? 'var(--accent-red-glow)' : 'var(--accent-orange-dim)'}`,
                      padding: '0.25rem 0.75rem',
                      borderRadius: '999px',
                      fontSize: '0.75rem',
                      fontWeight: '700',
                      textTransform: 'uppercase',
                      boxShadow: alert.severity === 'critical' ? '0 0 10px var(--accent-red-dim)' : 'none'
                    }}>
                      {alert.severity}
                    </span>
                  </td>
                  <td style={{ padding: '1.25rem', fontFamily: 'var(--font-mono)' }}>
                    {(alert.confidence * 100).toFixed(1)}%
                  </td>
                  <td style={{ padding: '1.25rem' }}>
                    <span style={{ color: 'var(--accent-red)', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', fontWeight: '600' }}>
                      <ShieldAlert size={14} /> Blocked
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      
      {/* Detailed Report Modal */}
      <ThreatModal alert={selectedAlert} onClose={() => setSelectedAlert(null)} />
    </div>
  );
}
