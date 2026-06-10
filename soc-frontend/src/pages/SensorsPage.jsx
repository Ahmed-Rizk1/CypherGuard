/**
 * SensorsPage — Sensor management dashboard.
 */
import { useState, useEffect } from 'react';
import { useAuth } from '../hooks/AuthContext';
import axios from 'axios';
import RBACGate from '../components/RBACGate';

export default function SensorsPage() {
  const { token } = useAuth();
  const [sensors, setSensors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newKey, setNewKey] = useState('');
  const [error, setError] = useState('');

  const headers = { Authorization: `Bearer ${token}` };

  const fetchSensors = async () => {
    try {
      const res = await axios.get('/v1/api/sensors', { headers });
      setSensors(res.data?.data || []);
    } catch { /* ignore */ }
    setLoading(false);
  };

  useEffect(() => { fetchSensors(); }, []);

  const createSensor = async () => {
    try {
      const res = await axios.post('/v1/api/sensors', { name: newName }, { headers });
      setNewKey(res.data?.data?.api_key || '');
      setNewName('');
      fetchSensors();
    } catch (err) {
      setError(err.response?.data?.error?.message || 'Failed to create sensor');
    }
  };

  const revokeSensor = async (id) => {
    if (!confirm('Revoke this sensor? It will stop sending data.')) return;
    try {
      await axios.delete(`/v1/api/sensors/${id}`, { headers });
      fetchSensors();
    } catch { /* ignore */ }
  };

  const statusColors = {
    active: '#10b981',
    pending: '#f59e0b',
    offline: '#ef4444',
    revoked: '#6b7280',
  };

  return (
    <div className="page-content">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h1 style={{ color: '#fff', fontSize: '22px' }}>📡 Sensors</h1>
        <RBACGate minRole="admin">
          <button className="btn-primary" onClick={() => { setShowCreate(true); setNewKey(''); setError(''); }}>
            + Add Sensor
          </button>
        </RBACGate>
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="card" style={{ marginBottom: '24px', border: '1px solid #00d4ff20' }}>
          {newKey ? (
            <div>
              <h3 style={{ color: '#10b981', marginBottom: '12px' }}>✅ Sensor Created!</h3>
              <p style={{ color: '#f59e0b', fontSize: '13px', marginBottom: '12px' }}>
                ⚠️ Save this API key now — it won't be shown again.
              </p>
              <div style={{
                background: '#0d1117',
                padding: '12px',
                borderRadius: '6px',
                fontFamily: 'monospace',
                fontSize: '13px',
                color: '#00d4ff',
                wordBreak: 'break-all',
              }}>
                {newKey}
              </div>
              <button
                onClick={() => { navigator.clipboard.writeText(newKey); }}
                style={{ marginTop: '12px', padding: '6px 16px', background: '#1e2a3a', border: 'none', color: '#fff', borderRadius: '6px', cursor: 'pointer' }}
              >
                📋 Copy Key
              </button>
              <button onClick={() => setShowCreate(false)} style={{ marginLeft: '8px', padding: '6px 16px', background: 'transparent', border: '1px solid #2d3a4d', color: '#9ca3af', borderRadius: '6px', cursor: 'pointer' }}>
                Done
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', gap: '12px', alignItems: 'end' }}>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', marginBottom: '6px', color: '#9ca3af', fontSize: '13px' }}>Sensor Name</label>
                <input
                  type="text"
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  className="form-input"
                  placeholder="e.g., AWS VPC East"
                />
              </div>
              <button className="btn-primary" onClick={createSensor} disabled={!newName}>
                Create
              </button>
              <button onClick={() => setShowCreate(false)} style={{ padding: '10px 16px', background: 'transparent', border: '1px solid #2d3a4d', color: '#9ca3af', borderRadius: '8px', cursor: 'pointer' }}>
                Cancel
              </button>
            </div>
          )}
          {error && <div className="form-error" style={{ marginTop: '8px' }}>{error}</div>}
        </div>
      )}

      {/* Sensor List */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px', color: '#6b7280' }}>Loading...</div>
      ) : sensors.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px' }}>
          <span style={{ fontSize: '40px' }}>📡</span>
          <p style={{ color: '#6b7280', marginTop: '12px' }}>No sensors deployed yet</p>
          <RBACGate minRole="admin">
            <button className="btn-primary" onClick={() => setShowCreate(true)} style={{ marginTop: '16px' }}>
              Deploy Your First Sensor
            </button>
          </RBACGate>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '12px' }}>
          {sensors.map(s => (
            <div key={s.id} className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                background: statusColors[s.status] || '#6b7280',
                boxShadow: s.status === 'active' ? `0 0 8px ${statusColors.active}` : 'none',
              }} />
              <div style={{ flex: 1 }}>
                <div style={{ color: '#fff', fontWeight: 600, fontSize: '14px' }}>{s.name}</div>
                <div style={{ color: '#6b7280', fontSize: '12px', marginTop: '2px' }}>
                  Key: {s.api_key_prefix}•••• &nbsp;|&nbsp; {s.status.toUpperCase()}
                  {s.last_heartbeat && ` | Last seen: ${new Date(s.last_heartbeat).toLocaleString()}`}
                  {s.version && ` | v${s.version}`}
                </div>
              </div>
              <RBACGate minRole="admin">
                {s.status !== 'revoked' && (
                  <button
                    onClick={() => revokeSensor(s.id)}
                    style={{
                      padding: '6px 14px',
                      background: 'transparent',
                      border: '1px solid #ef4444',
                      color: '#ef4444',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      fontSize: '12px',
                    }}
                  >
                    Revoke
                  </button>
                )}
              </RBACGate>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
