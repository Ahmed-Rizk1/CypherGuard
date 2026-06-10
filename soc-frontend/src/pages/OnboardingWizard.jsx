/**
 * OnboardingWizard — 4-step onboarding for new tenants.
 * Steps: Welcome → Deploy Sensor → Waiting for Data → Invite Team
 */
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/AuthContext';
import axios from 'axios';

const STEPS = [
  { key: 'welcome', title: 'Welcome', icon: '👋' },
  { key: 'sensor', title: 'Deploy Sensor', icon: '📡' },
  { key: 'waiting', title: 'Verify Connection', icon: '🔍' },
  { key: 'team', title: 'Invite Team', icon: '👥' },
];

export default function OnboardingWizard() {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [status, setStatus] = useState(null);
  const [sensorKey, setSensorKey] = useState('');
  const [sensorName, setSensorName] = useState('Main Office');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('analyst');
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');

  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await axios.get('/v1/api/onboarding/status', { headers });
        setStatus(res.data?.data);
      } catch { /* ignore */ }
    };
    fetchStatus();
  }, [step]);

  const createSensor = async () => {
    setLoading(true);
    try {
      const res = await axios.post('/v1/api/sensors', { name: sensorName }, { headers });
      setSensorKey(res.data?.data?.api_key || '');
      setStep(2);
    } catch (err) {
      setMsg(err.response?.data?.error?.message || 'Failed to create sensor');
    }
    setLoading(false);
  };

  const sendInvite = async () => {
    setLoading(true);
    try {
      await axios.post('/v1/api/team/invite', { email: inviteEmail, role: inviteRole }, { headers });
      setMsg(`Invitation sent to ${inviteEmail}`);
      setInviteEmail('');
    } catch (err) {
      setMsg(err.response?.data?.error?.message || 'Failed to send invite');
    }
    setLoading(false);
  };

  const finish = () => navigate('/app');

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#0a0e17',
      padding: '40px 20px',
    }}>
      {/* Progress Steps */}
      <div style={{ display: 'flex', gap: '24px', marginBottom: '40px' }}>
        {STEPS.map((s, i) => (
          <div key={s.key} style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            opacity: i <= step ? 1 : 0.4,
          }}>
            <span style={{
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: i < step ? '#00d4ff' : i === step ? '#1e2a3a' : '#0d1117',
              border: i === step ? '2px solid #00d4ff' : 'none',
              fontSize: '14px',
            }}>
              {i < step ? '✓' : s.icon}
            </span>
            <span style={{ color: '#fff', fontSize: '13px', fontWeight: i === step ? 600 : 400 }}>
              {s.title}
            </span>
            {i < STEPS.length - 1 && (
              <div style={{ width: '30px', height: '2px', background: i < step ? '#00d4ff' : '#1e2a3a' }} />
            )}
          </div>
        ))}
      </div>

      {/* Step Content */}
      <div style={{
        background: '#141b2d',
        borderRadius: '16px',
        border: '1px solid #1e2a3a',
        padding: '48px',
        maxWidth: '560px',
        width: '100%',
        textAlign: 'center',
      }}>
        {step === 0 && (
          <>
            <h1 style={{ fontSize: '28px', color: '#fff', marginBottom: '12px' }}>
              Welcome to SecureNet! 🎉
            </h1>
            <p style={{ color: '#9ca3af', lineHeight: 1.7, marginBottom: '32px' }}>
              Let's get your security operations center set up in under 5 minutes.
              We'll deploy a sensor on your network and start detecting threats immediately.
            </p>
            <button className="btn-primary" onClick={() => setStep(1)} style={{ width: '100%' }}>
              Let's Go →
            </button>
          </>
        )}

        {step === 1 && (
          <>
            <h2 style={{ color: '#fff', marginBottom: '20px' }}>Deploy Your First Sensor</h2>
            <p style={{ color: '#9ca3af', marginBottom: '24px', fontSize: '14px' }}>
              Name your sensor and we'll generate an API key for it.
            </p>
            <div className="form-group" style={{ textAlign: 'left' }}>
              <label htmlFor="sensorName">Sensor Name</label>
              <input
                id="sensorName"
                type="text"
                value={sensorName}
                onChange={e => setSensorName(e.target.value)}
                className="form-input"
                placeholder="e.g., Main Office, AWS VPC"
              />
            </div>
            {msg && <div className="form-error">{msg}</div>}
            <button className="btn-primary" onClick={createSensor} disabled={loading} style={{ width: '100%' }}>
              {loading ? 'Creating...' : 'Create Sensor →'}
            </button>
          </>
        )}

        {step === 2 && (
          <>
            <h2 style={{ color: '#fff', marginBottom: '20px' }}>Run the Sensor</h2>
            <p style={{ color: '#9ca3af', marginBottom: '16px', fontSize: '14px' }}>
              Copy this command and run it on the machine you want to monitor:
            </p>
            <div style={{
              background: '#0d1117',
              borderRadius: '8px',
              padding: '16px',
              fontFamily: 'monospace',
              fontSize: '12px',
              color: '#00d4ff',
              wordBreak: 'break-all',
              textAlign: 'left',
              marginBottom: '16px',
            }}>
              docker run -d --name securenet-sensor \<br />
              &nbsp;&nbsp;-e SECURENET_API_KEY={sensorKey} \<br />
              &nbsp;&nbsp;-e SECURENET_ENDPOINT=http://your-server:8007 \<br />
              &nbsp;&nbsp;--network host \<br />
              &nbsp;&nbsp;securenet/sensor:latest
            </div>
            <button
              onClick={() => {navigator.clipboard.writeText(
                `docker run -d --name securenet-sensor -e SECURENET_API_KEY=${sensorKey} -e SECURENET_ENDPOINT=http://your-server:8007 --network host securenet/sensor:latest`
              ); setMsg('Copied!'); setTimeout(() => setMsg(''), 2000);}}
              style={{
                background: '#1e2a3a',
                border: 'none',
                color: '#fff',
                padding: '8px 20px',
                borderRadius: '6px',
                cursor: 'pointer',
                marginBottom: '20px',
              }}
            >
              {msg === 'Copied!' ? '✓ Copied' : '📋 Copy Command'}
            </button>
            <br />
            <button className="btn-primary" onClick={() => setStep(3)} style={{ width: '100%', marginTop: '8px' }}>
              Continue →
            </button>
          </>
        )}

        {step === 3 && (
          <>
            <h2 style={{ color: '#fff', marginBottom: '20px' }}>Invite Your Team</h2>
            <p style={{ color: '#9ca3af', marginBottom: '24px', fontSize: '14px' }}>
              Security is a team effort. Invite your analysts and admins.
            </p>
            <div className="form-group" style={{ textAlign: 'left' }}>
              <label htmlFor="inviteEmail">Email Address</label>
              <input
                id="inviteEmail"
                type="email"
                value={inviteEmail}
                onChange={e => setInviteEmail(e.target.value)}
                className="form-input"
                placeholder="colleague@company.com"
              />
            </div>
            <div className="form-group" style={{ textAlign: 'left' }}>
              <label htmlFor="inviteRole">Role</label>
              <select
                id="inviteRole"
                value={inviteRole}
                onChange={e => setInviteRole(e.target.value)}
                className="form-input"
              >
                <option value="admin">Admin</option>
                <option value="analyst">Analyst</option>
                <option value="viewer">Viewer</option>
              </select>
            </div>
            {msg && <div style={{ color: msg.includes('sent') ? '#10b981' : '#ef4444', fontSize: '13px', marginBottom: '12px' }}>{msg}</div>}
            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                onClick={sendInvite}
                disabled={loading || !inviteEmail}
                style={{
                  flex: 1,
                  padding: '10px',
                  background: '#1e2a3a',
                  border: '1px solid #2d3a4d',
                  color: '#fff',
                  borderRadius: '8px',
                  cursor: 'pointer',
                }}
              >
                {loading ? 'Sending...' : 'Send Invite'}
              </button>
              <button className="btn-primary" onClick={finish} style={{ flex: 1 }}>
                Go to Dashboard →
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
