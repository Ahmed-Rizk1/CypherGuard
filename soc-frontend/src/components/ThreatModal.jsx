import { X, ShieldAlert, Cpu, Network, FileCode, AlertTriangle, Crosshair } from 'lucide-react';
import { createPortal } from 'react-dom';
import { useEffect } from 'react';

export default function ThreatModal({ alert, onClose }) {
  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!alert) return null;

  return createPortal(
    <div 
      onClick={onClose}
      style={{
        position: 'fixed',
        top: 0, left: 0, right: 0, bottom: 0,
        background: 'rgba(0,0,0,0.8)',
        backdropFilter: 'blur(10px)',
        zIndex: 99999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem'
      }}
    >
      <div 
        className="animate-slide-in" 
        onClick={(e) => e.stopPropagation()} 
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--accent-red)',
          boxShadow: '0 0 40px rgba(255, 42, 84, 0.2)',
          borderRadius: '12px',
          width: '100%',
          maxWidth: '800px',
          maxHeight: '90vh',
          overflowY: 'auto',
          position: 'relative'
        }}
      >
        {/* Header */}
        <div style={{ 
          background: 'rgba(255, 42, 84, 0.1)', 
          padding: '1.5rem 2rem', 
          borderBottom: '1px solid var(--border-color)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
              <ShieldAlert size={28} color="var(--accent-red)" />
              <h2 style={{ fontSize: '1.5rem', margin: 0 }}>Cyber-Intelligence Report</h2>
            </div>
            <p style={{ color: 'var(--text-secondary)', margin: 0, fontFamily: 'var(--font-mono)' }}>
              REPORT ID: {alert.alert_id} | TIMESTAMP: {new Date(alert.timestamp).toLocaleString()}
            </p>
          </div>
          <button 
            onClick={onClose}
            style={{ 
              background: 'transparent', 
              border: 'none', 
              color: 'var(--text-muted)', 
              cursor: 'pointer' 
            }}
          >
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          {/* Top Stats */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem' }}>
            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '1rem', borderRadius: '8px', borderLeft: '3px solid var(--accent-purple)' }}>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase', marginBottom: '0.5rem' }}><Network size={14} style={{ display:'inline', verticalAlign:'text-bottom'}} /> Origin</p>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.2rem', color: 'var(--text-primary)' }}>
                {alert.src_ip} {alert.country ? `(${alert.country})` : ''}
              </div>
            </div>
            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '1rem', borderRadius: '8px', borderLeft: '3px solid var(--accent-red)' }}>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase', marginBottom: '0.5rem' }}><Crosshair size={14} style={{ display:'inline', verticalAlign:'text-bottom'}} /> Classification</p>
              <div style={{ fontWeight: '600', fontSize: '1.1rem', color: 'var(--accent-red)' }}>
                {alert.attack_type}
              </div>
            </div>
            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '1rem', borderRadius: '8px', borderLeft: '3px solid var(--accent-cyan)' }}>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase', marginBottom: '0.5rem' }}><Cpu size={14} style={{ display:'inline', verticalAlign:'text-bottom'}} /> Analyzer Source</p>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', color: 'var(--accent-cyan)' }}>
                {alert._source} (Conf: {(alert.confidence * 100).toFixed(1)}%)
              </div>
            </div>
          </div>

          {/* AI Explanation */}
          <div>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-primary)', marginBottom: '1rem' }}>
              <AlertTriangle size={18} color="var(--accent-orange)" /> Threat Analysis
            </h3>
            <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1.5rem', borderRadius: '8px', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
              {alert.explanation}
            </div>
          </div>

          {/* MITRE & CVE (If available) */}
          {(alert.mitre_tactic || alert.cve) && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
              <div>
                <h3 style={{ color: 'var(--text-primary)', marginBottom: '1rem', fontSize: '1rem' }}>MITRE ATT&CK Mapping</h3>
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '8px', border: '1px dashed var(--border-highlight)', fontFamily: 'var(--font-mono)' }}>
                  <div style={{ marginBottom: '0.5rem' }}><span style={{ color: 'var(--text-muted)' }}>Tactic:</span> <span style={{ color: 'var(--accent-purple)' }}>{alert.mitre_tactic || 'Unknown'}</span></div>
                  <div><span style={{ color: 'var(--text-muted)' }}>Technique:</span> <span style={{ color: 'var(--accent-cyan)' }}>{alert.mitre_technique || 'Unknown'}</span></div>
                </div>
              </div>
              <div>
                <h3 style={{ color: 'var(--text-primary)', marginBottom: '1rem', fontSize: '1rem' }}>Vulnerability Reference</h3>
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '8px', border: '1px dashed var(--border-highlight)', fontFamily: 'var(--font-mono)' }}>
                  <span style={{ color: 'var(--text-muted)' }}>CVE ID:</span> <span style={{ color: 'var(--accent-orange)' }}>{alert.cve || 'N/A'}</span>
                </div>
              </div>
            </div>
          )}

          {/* Remediation */}
          <div>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-primary)', marginBottom: '1rem' }}>
              <FileCode size={18} color="var(--accent-green)" /> Remediation Steps
            </h3>
            <div style={{ background: 'rgba(16, 185, 129, 0.05)', padding: '1.5rem', borderRadius: '8px', border: '1px solid rgba(16, 185, 129, 0.2)', color: 'var(--text-secondary)' }}>
              {alert.recommendation.split('\\n').map((step, idx) => (
                <div key={idx} style={{ marginBottom: '0.5rem' }}>{step}</div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>,
    document.body
  );
}
