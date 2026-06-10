/**
 * useSOCData — Custom React hook for WebSocket-based real-time SOC data.
 *
 * Replaces three separate polling intervals (axios.get) with a single
 * WebSocket connection to the API Gateway. Handles auto-reconnect,
 * heartbeat, and connection status tracking.
 *
 * Now accepts a JWT token for authenticated WebSocket connections.
 */
import { useState, useEffect, useRef, useCallback } from 'react';

const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_BASE = import.meta.env.VITE_WS_URL || `${wsProtocol}//${window.location.host}/ws/telemetry`;
const MAX_HISTORY = 60;

export function useSOCData(token) {
  const [metrics, setMetrics] = useState({
    packets_per_sec: 0,
    bytes_per_sec: 0,
    active_connections: 0,
  });

  const [history, setHistory] = useState(() =>
    Array.from({ length: MAX_HISTORY }, () => ({
      time: '',
      packets: 0,
      bytes: 0,
    }))
  );

  const [blockedIps, setBlockedIps] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState('connecting');

  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const retryCount = useRef(0);

  const connect = useCallback(() => {
    if (!token) {
      setConnectionStatus('unauthenticated');
      return;
    }
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setConnectionStatus('connecting');
    // Pass JWT token as query parameter for WebSocket authentication
    const wsUrl = `${WS_BASE}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnectionStatus('connected');
      retryCount.current = 0; // Reset backoff on success
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        switch (msg.type) {
          case 'metrics':
            setMetrics(msg.data);
            setHistory((prev) => {
              const next = [...prev.slice(1)];
              next.push({
                time: new Date().toLocaleTimeString('en-US', { hour12: false }),
                packets: msg.data.packets_per_sec || 0,
                bytes: msg.data.bytes_per_sec || 0,
              });
              return next;
            });
            break;

          case 'blocked_ips':
            setBlockedIps(msg.data || []);
            break;

          case 'alert_list':
            setAlerts(msg.data || []);
            break;

          case 'new_alert':
            setAlerts((prev) => [msg.data, ...prev].slice(0, 50));
            break;

          case 'heartbeat':
          case 'pong':
            break;

          case 'token_expired':
            // Server signals the JWT has expired — session will close
            setConnectionStatus('token_expired');
            break;

          default:
            break;
        }
      } catch (e) {
        console.error('[WS] Parse error:', e);
      }
    };

    ws.onclose = (event) => {
      setConnectionStatus('disconnected');
      wsRef.current = null;
      // Don't reconnect if auth failure (4001)
      if (event.code === 4001) {
        setConnectionStatus('auth_failed');
        return;
      }
      
      // Exponential backoff: 1s, 2s, 4s, 8s... max 30s
      let delay = Math.min(1000 * Math.pow(2, retryCount.current), 30000);
      delay += Math.random() * 500; // Add jitter
      
      reconnectTimer.current = setTimeout(connect, delay);
      retryCount.current += 1;
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [token]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      clearTimeout(reconnectTimer.current);
    };
  }, [connect]);

  return { metrics, history, blockedIps, alerts, connectionStatus };
}
