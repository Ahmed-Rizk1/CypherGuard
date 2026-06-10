/**
 * TeamPage — Team management and invitations.
 */
import { useState, useEffect } from 'react';
import { useAuth } from '../hooks/AuthContext';
import axios from 'axios';
import RBACGate from '../components/RBACGate';

export default function TeamPage() {
  const { token, user } = useAuth();
  const [members, setMembers] = useState([]);
  const [invites, setInvites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showInvite, setShowInvite] = useState(false);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('analyst');
  const [msg, setMsg] = useState('');

  const headers = { Authorization: `Bearer ${token}` };

  const fetchTeam = async () => {
    try {
      const res = await axios.get('/v1/api/team', { headers });
      setMembers(res.data?.data?.members || []);
      setInvites(res.data?.data?.pending_invitations || []);
    } catch { /* ignore */ }
    setLoading(false);
  };

  useEffect(() => { fetchTeam(); }, []);

  const sendInvite = async () => {
    try {
      await axios.post('/v1/api/team/invite', { email, role }, { headers });
      setMsg(`Invitation sent to ${email}`);
      setEmail('');
      fetchTeam();
    } catch (err) {
      setMsg(err.response?.data?.error?.message || 'Failed to send invite');
    }
  };

  const roleColors = {
    owner: '#f59e0b',
    admin: '#8b5cf6',
    analyst: '#00d4ff',
    viewer: '#6b7280',
  };

  return (
    <div className="page-content">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h1 style={{ color: '#fff', fontSize: '22px' }}>👥 Team</h1>
        <RBACGate minRole="admin">
          <button className="btn-primary" onClick={() => setShowInvite(!showInvite)}>
            + Invite Member
          </button>
        </RBACGate>
      </div>

      {/* Invite Form */}
      {showInvite && (
        <div className="card" style={{ marginBottom: '24px', border: '1px solid #00d4ff20' }}>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'end' }}>
            <div style={{ flex: 2 }}>
              <label style={{ display: 'block', marginBottom: '6px', color: '#9ca3af', fontSize: '13px' }}>Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="form-input"
                placeholder="colleague@company.com"
              />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', marginBottom: '6px', color: '#9ca3af', fontSize: '13px' }}>Role</label>
              <select value={role} onChange={e => setRole(e.target.value)} className="form-input">
                <option value="admin">Admin</option>
                <option value="analyst">Analyst</option>
                <option value="viewer">Viewer</option>
              </select>
            </div>
            <button className="btn-primary" onClick={sendInvite} disabled={!email}>Send</button>
          </div>
          {msg && <div style={{ marginTop: '8px', fontSize: '13px', color: msg.includes('sent') ? '#10b981' : '#ef4444' }}>{msg}</div>}
        </div>
      )}

      {/* Members */}
      <h3 style={{ color: '#9ca3af', fontSize: '13px', textTransform: 'uppercase', marginBottom: '12px' }}>Members</h3>
      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px', color: '#6b7280' }}>Loading...</div>
      ) : (
        <div style={{ display: 'grid', gap: '8px', marginBottom: '32px' }}>
          {members.map(m => (
            <div key={m.id} className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px', padding: '14px 20px' }}>
              <div style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                background: `${roleColors[m.role] || '#6b7280'}20`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: roleColors[m.role],
                fontWeight: 700,
                fontSize: '14px',
              }}>
                {(m.full_name || m.email)[0].toUpperCase()}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ color: '#fff', fontWeight: 500, fontSize: '14px' }}>
                  {m.full_name || m.email}
                  {m.id === user?.user_id && <span style={{ color: '#6b7280', fontSize: '12px' }}> (you)</span>}
                </div>
                <div style={{ color: '#6b7280', fontSize: '12px' }}>{m.email}</div>
              </div>
              <span style={{
                padding: '3px 10px',
                borderRadius: '4px',
                fontSize: '11px',
                fontWeight: 600,
                textTransform: 'uppercase',
                color: roleColors[m.role],
                background: `${roleColors[m.role]}15`,
              }}>
                {m.role}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Pending Invitations */}
      {invites.length > 0 && (
        <>
          <h3 style={{ color: '#9ca3af', fontSize: '13px', textTransform: 'uppercase', marginBottom: '12px' }}>Pending Invitations</h3>
          <div style={{ display: 'grid', gap: '8px' }}>
            {invites.map((inv, i) => (
              <div key={i} className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px', padding: '14px 20px', opacity: 0.7 }}>
                <span style={{ fontSize: '20px' }}>✉️</span>
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#fff', fontSize: '14px' }}>{inv.email}</div>
                  <div style={{ color: '#6b7280', fontSize: '12px' }}>
                    Invited as {inv.role} • {new Date(inv.created_at).toLocaleDateString()}
                  </div>
                </div>
                <span style={{
                  padding: '3px 10px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  color: '#f59e0b',
                  background: '#f59e0b15',
                }}>
                  PENDING
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
