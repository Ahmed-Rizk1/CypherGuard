/**
 * NotificationCenter — Bell icon dropdown with recent notifications.
 */
import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../hooks/AuthContext';
import axios from 'axios';

export default function NotificationCenter() {
  const { token } = useAuth();
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!token) return;
    const fetchNotifications = async () => {
      try {
        const res = await axios.get('/v1/api/notifications', {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.data?.success) {
          setNotifications(res.data.data.items || []);
          setUnreadCount(res.data.data.unread_count || 0);
        }
      } catch { /* ignore */ }
    };
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, [token]);

  // Close on outside click
  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setIsOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const markRead = async (id) => {
    try {
      await axios.post(`/v1/api/notifications/${id}/read`, null, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setNotifications(prev =>
        prev.map(n => n.id === id ? { ...n, read_at: new Date().toISOString() } : n)
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch { /* ignore */ }
  };

  const typeIcons = { alert: '🚨', sensor: '📡', billing: '💳', system: '⚙️' };

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontSize: '20px',
          position: 'relative',
          padding: '8px',
          color: '#9ca3af',
        }}
        title="Notifications"
      >
        🔔
        {unreadCount > 0 && (
          <span style={{
            position: 'absolute',
            top: '2px',
            right: '2px',
            background: '#ef4444',
            color: '#fff',
            borderRadius: '50%',
            width: '18px',
            height: '18px',
            fontSize: '11px',
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div style={{
          position: 'absolute',
          right: 0,
          top: '100%',
          width: '360px',
          maxHeight: '480px',
          overflowY: 'auto',
          background: '#141b2d',
          border: '1px solid #1e2a3a',
          borderRadius: '12px',
          boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
          zIndex: 1000,
        }}>
          <div style={{
            padding: '14px 16px',
            borderBottom: '1px solid #1e2a3a',
            fontWeight: 600,
            fontSize: '14px',
            color: '#fff',
          }}>
            Notifications
          </div>
          {notifications.length === 0 ? (
            <div style={{ padding: '40px 16px', textAlign: 'center', color: '#6b7280', fontSize: '13px' }}>
              No notifications yet
            </div>
          ) : (
            notifications.map(n => (
              <div
                key={n.id}
                onClick={() => !n.read_at && markRead(n.id)}
                style={{
                  padding: '12px 16px',
                  borderBottom: '1px solid #0d1117',
                  cursor: n.read_at ? 'default' : 'pointer',
                  background: n.read_at ? 'transparent' : 'rgba(0, 212, 255, 0.03)',
                  transition: 'background 0.15s',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'start', gap: '10px' }}>
                  <span style={{ fontSize: '16px' }}>{typeIcons[n.type] || '📌'}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontWeight: n.read_at ? 400 : 600,
                      fontSize: '13px',
                      color: n.read_at ? '#9ca3af' : '#fff',
                    }}>
                      {n.title}
                    </div>
                    <div style={{
                      fontSize: '12px',
                      color: '#6b7280',
                      marginTop: '2px',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}>
                      {n.message}
                    </div>
                    <div style={{ fontSize: '11px', color: '#4b5563', marginTop: '4px' }}>
                      {new Date(n.created_at).toLocaleString()}
                    </div>
                  </div>
                  {!n.read_at && (
                    <span style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      background: '#00d4ff',
                      flexShrink: 0,
                      marginTop: '4px',
                    }} />
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
