import { useState } from 'react';
import { motion } from 'framer-motion';
import { Settings, Shield, Brain, Bell, Monitor, Save, CheckCircle, RotateCcw } from 'lucide-react';

export default function SettingsPage() {
  const [saved, setSaved] = useState(false);
  const [settings, setSettings] = useState({
    mlStrictness: 75,
    autoBlock: true,
    blockThreshold: 3,
    alertSound: true,
    darkMode: true,
    emailAlerts: false,
    slackIntegration: false,
    retentionDays: 30,
    maxBlocklistSize: 500,
    refreshInterval: 2,
  });

  const updateSetting = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const handleReset = () => {
    setSettings({
      mlStrictness: 75,
      autoBlock: true,
      blockThreshold: 3,
      alertSound: true,
      darkMode: true,
      emailAlerts: false,
      slackIntegration: false,
      retentionDays: 30,
      maxBlocklistSize: 500,
      refreshInterval: 2,
    });
    setSaved(false);
  };

  const Toggle = ({ checked, onChange }) => (
    <div 
      onClick={() => onChange(!checked)}
      style={{
        width: '48px', height: '26px', borderRadius: '999px',
        background: checked ? 'var(--accent-cyan)' : 'rgba(255,255,255,0.1)',
        cursor: 'pointer', position: 'relative', transition: 'background 0.3s',
        border: `1px solid ${checked ? 'var(--accent-cyan)' : 'var(--border-color)'}`
      }}
    >
      <motion.div
        animate={{ x: checked ? 22 : 2 }}
        transition={{ type: 'spring', stiffness: 500, damping: 30 }}
        style={{
          width: '20px', height: '20px', borderRadius: '50%',
          background: '#fff', position: 'absolute', top: '2px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.3)'
        }}
      />
    </div>
  );

  const Slider = ({ value, min, max, step, onChange, unit, color }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
      <input
        type="range"
        min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{
          flex: 1, height: '6px', appearance: 'none', background: `linear-gradient(90deg, ${color || 'var(--accent-cyan)'} ${((value - min) / (max - min)) * 100}%, rgba(255,255,255,0.1) 0%)`,
          borderRadius: '999px', outline: 'none', cursor: 'pointer'
        }}
      />
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9rem', fontWeight: '600', minWidth: '60px', textAlign: 'right' }}>
        {value}{unit || ''}
      </span>
    </div>
  );

  const SectionHeader = ({ icon: Icon, title }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
      <Icon size={18} color="var(--accent-cyan)" />
      <h3 style={{ fontSize: '1.1rem', fontWeight: '600' }}>{title}</h3>
    </div>
  );

  const SettingRow = ({ label, description, children }) => (
    <div style={{ 
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '1rem 0', borderBottom: '1px solid rgba(255,255,255,0.05)'
    }}>
      <div style={{ flex: 1, marginRight: '2rem' }}>
        <div style={{ fontWeight: '500', marginBottom: '0.2rem' }}>{label}</div>
        {description && <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{description}</div>}
      </div>
      <div style={{ minWidth: '200px', display: 'flex', justifyContent: 'flex-end' }}>
        {children}
      </div>
    </div>
  );

  return (
    <div className="dashboard-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>System Settings</h1>
          <p style={{ color: 'var(--text-secondary)' }}>Configure detection sensitivity, firewall rules, and notification preferences.</p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button onClick={handleReset} style={{
            background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-color)', color: 'var(--text-secondary)',
            padding: '0.6rem 1.25rem', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '0.85rem',
            display: 'flex', alignItems: 'center', gap: '0.5rem', transition: 'all 0.2s'
          }}>
            <RotateCcw size={14} /> Reset to Defaults
          </button>
          <button onClick={handleSave} style={{
            background: saved ? 'var(--accent-green)' : 'var(--accent-cyan)', border: 'none', color: '#000',
            padding: '0.6rem 1.5rem', borderRadius: '8px', cursor: 'pointer', fontWeight: '700', fontSize: '0.85rem',
            display: 'flex', alignItems: 'center', gap: '0.5rem', transition: 'all 0.3s',
            boxShadow: saved ? '0 0 20px rgba(16, 185, 129, 0.3)' : '0 0 20px rgba(0, 242, 254, 0.3)'
          }}>
            {saved ? <><CheckCircle size={14} /> Saved!</> : <><Save size={14} /> Save Changes</>}
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
        {/* ML Engine Settings */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <SectionHeader icon={Brain} title="ML Detection Engine" />
          
          <SettingRow label="Detection Strictness" description="Higher values reduce false negatives but may increase false positives.">
            <Slider value={settings.mlStrictness} min={0} max={100} step={5} onChange={(v) => updateSetting('mlStrictness', v)} unit="%" color="var(--accent-purple)" />
          </SettingRow>

          <SettingRow label="Auto-Block Malicious IPs" description="Automatically block IPs flagged as malicious by the ML engine.">
            <Toggle checked={settings.autoBlock} onChange={(v) => updateSetting('autoBlock', v)} />
          </SettingRow>

          <SettingRow label="Block Threshold (Alerts)" description="Number of alerts from same IP before auto-blocking.">
            <Slider value={settings.blockThreshold} min={1} max={10} step={1} onChange={(v) => updateSetting('blockThreshold', v)} unit=" hits" color="var(--accent-orange)" />
          </SettingRow>
        </div>

        {/* Firewall Settings */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <SectionHeader icon={Shield} title="Firewall Policies" />

          <SettingRow label="Max Blocklist Size" description="Maximum number of IPs that can be simultaneously blocked.">
            <Slider value={settings.maxBlocklistSize} min={100} max={2000} step={100} onChange={(v) => updateSetting('maxBlocklistSize', v)} unit=" IPs" color="var(--accent-cyan)" />
          </SettingRow>

          <SettingRow label="Data Retention Period" description="How long to keep historical alerts and blocked IPs.">
            <Slider value={settings.retentionDays} min={7} max={90} step={1} onChange={(v) => updateSetting('retentionDays', v)} unit=" days" color="var(--accent-green)" />
          </SettingRow>

          <SettingRow label="Telemetry Refresh Interval" description="How often the dashboard polls the backend for new data.">
            <Slider value={settings.refreshInterval} min={1} max={10} step={1} onChange={(v) => updateSetting('refreshInterval', v)} unit="s" color="var(--accent-cyan)" />
          </SettingRow>
        </div>

        {/* Notifications */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <SectionHeader icon={Bell} title="Notifications" />

          <SettingRow label="Alert Sound Effects" description="Play an audible alert when a critical threat is detected.">
            <Toggle checked={settings.alertSound} onChange={(v) => updateSetting('alertSound', v)} />
          </SettingRow>

          <SettingRow label="Email Notifications" description="Send email to SOC team on critical detections.">
            <Toggle checked={settings.emailAlerts} onChange={(v) => updateSetting('emailAlerts', v)} />
          </SettingRow>

          <SettingRow label="Slack Integration" description="Forward alerts to a Slack channel via webhook.">
            <Toggle checked={settings.slackIntegration} onChange={(v) => updateSetting('slackIntegration', v)} />
          </SettingRow>
        </div>

        {/* Display */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <SectionHeader icon={Monitor} title="Display & Interface" />

          <SettingRow label="Dark Mode" description="Toggle between dark and light interface themes.">
            <Toggle checked={settings.darkMode} onChange={(v) => updateSetting('darkMode', v)} />
          </SettingRow>

          <div style={{ padding: '1rem 0' }}>
            <div style={{ fontWeight: '500', marginBottom: '0.75rem' }}>System Information</div>
            <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: '8px', padding: '1rem', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
              {[
                { k: 'Version', v: 'SecureNet SOC v3.2.1' },
                { k: 'Engine', v: 'AI Analyzer V2 (Mock LLM)' },
                { k: 'Backend', v: 'FastAPI / Uvicorn' },
                { k: 'Frontend', v: 'React 18 + Vite' },
                { k: 'License', v: 'Academic — Graduation Project' },
              ].map((item, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.3rem 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                  <span style={{ color: 'var(--text-muted)' }}>{item.k}</span>
                  <span style={{ color: 'var(--accent-cyan)' }}>{item.v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
