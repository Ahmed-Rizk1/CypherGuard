import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Globe, Shield, Server, Database, Activity, Cloud, RefreshCw, Power, CheckCircle2, AlertTriangle } from 'lucide-react';
import { useSOCDataContext } from '../hooks/SOCDataContext';

const NODES = [
  { id: 'internet', label: 'External Internet', icon: Globe, x: 50, y: 8, color: '#ef4444' },
  { id: 'firewall', label: 'Edge Firewall', icon: Shield, x: 50, y: 28, color: '#00f2fe' },
  { id: 'loadbalancer', label: 'Load Balancer', icon: Cloud, x: 50, y: 48, color: '#a855f7' },
  { id: 'web1', label: 'Web Server 01', icon: Server, x: 25, y: 68, color: '#3b82f6' },
  { id: 'web2', label: 'Web Server 02', icon: Server, x: 75, y: 68, color: '#3b82f6' },
  { id: 'db', label: 'PostgreSQL DB', icon: Database, x: 50, y: 88, color: '#f59e0b' },
];

const CONNECTIONS = [
  { from: 'internet', to: 'firewall' },
  { from: 'firewall', to: 'loadbalancer' },
  { from: 'loadbalancer', to: 'web1' },
  { from: 'loadbalancer', to: 'web2' },
  { from: 'web1', to: 'db' },
  { from: 'web2', to: 'db' },
];

export default function SystemNodes() {
  const { alerts, blockedIps, metrics } = useSOCDataContext();
  const [nodeStates, setNodeStates] = useState({});
  const [selectedNode, setSelectedNode] = useState(null);
  const [actionLog, setActionLog] = useState([]);

  const isUnderAttack = alerts.length > 3;

  // Simulate dynamic node health
  useEffect(() => {
    const states = {};
    NODES.forEach(n => {
      if (n.id === 'internet') {
        states[n.id] = { status: 'active', cpu: '-', mem: '-', uptime: '-' };
      } else {
        states[n.id] = {
          status: isUnderAttack && n.id === 'firewall' ? 'stressed' : 'healthy',
          cpu: `${Math.floor(Math.random() * 60) + (isUnderAttack ? 30 : 5)}%`,
          mem: `${Math.floor(Math.random() * 40) + 20}%`,
          uptime: '99.9%'
        };
      }
    });
    setNodeStates(states);
  }, [alerts.length, isUnderAttack]);

  const getNodePos = (id) => {
    const node = NODES.find(n => n.id === id);
    return { x: node.x, y: node.y };
  };

  const handleNodeAction = (nodeId, action) => {
    const timestamp = new Date().toLocaleTimeString();
    const node = NODES.find(n => n.id === nodeId);
    let msg = '';
    
    if (action === 'restart') {
      msg = `[${timestamp}] ⟳ Restarting ${node.label}...`;
      setNodeStates(prev => ({ ...prev, [nodeId]: { ...prev[nodeId], status: 'restarting' } }));
      setTimeout(() => {
        setNodeStates(prev => ({ ...prev, [nodeId]: { ...prev[nodeId], status: 'healthy' } }));
        setActionLog(prev => [`[${new Date().toLocaleTimeString()}] ✓ ${node.label} restarted successfully.`, ...prev]);
      }, 2000);
    } else if (action === 'shutdown') {
      msg = `[${timestamp}] ⏻ Shutting down ${node.label}...`;
      setNodeStates(prev => ({ ...prev, [nodeId]: { ...prev[nodeId], status: 'offline' } }));
    } else if (action === 'poweron') {
      msg = `[${timestamp}] ⏻ Powering on ${node.label}...`;
      setNodeStates(prev => ({ ...prev, [nodeId]: { ...prev[nodeId], status: 'restarting' } }));
      setTimeout(() => {
        setNodeStates(prev => ({ ...prev, [nodeId]: { ...prev[nodeId], status: 'healthy' } }));
        setActionLog(prev => [`[${new Date().toLocaleTimeString()}] ✓ ${node.label} is now online.`, ...prev]);
      }, 1500);
    }

    setActionLog(prev => [msg, ...prev].slice(0, 20));
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy': return 'var(--accent-green)';
      case 'stressed': return 'var(--accent-orange)';
      case 'offline': return 'var(--text-muted)';
      case 'restarting': return 'var(--accent-cyan)';
      default: return 'var(--text-secondary)';
    }
  };

  return (
    <div className="dashboard-container">
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>Network Architecture & Topology</h1>
        <p style={{ color: 'var(--text-secondary)' }}>Interactive map of all infrastructure nodes. Click a node to inspect & control it.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2.5fr 1fr', gap: '1.5rem' }}>
        {/* SVG Topology Map */}
        <div className="glass-panel" style={{ padding: '1rem', position: 'relative', minHeight: '550px' }}>
          <svg viewBox="0 0 100 100" style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }}>
            <defs>
              <linearGradient id="lineGradSafe" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="var(--accent-cyan)" stopOpacity="0.8" />
                <stop offset="100%" stopColor="var(--accent-purple)" stopOpacity="0.8" />
              </linearGradient>
              <linearGradient id="lineGradDanger" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#ef4444" stopOpacity="0.9" />
                <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.9" />
              </linearGradient>
              <filter id="glow">
                <feGaussianBlur stdDeviation="0.5" result="coloredBlur" />
                <feMerge>
                  <feMergeNode in="coloredBlur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {/* Connection lines */}
            {CONNECTIONS.map((conn, i) => {
              const from = getNodePos(conn.from);
              const to = getNodePos(conn.to);
              const isDanger = isUnderAttack && conn.from === 'internet';
              const isOffline = nodeStates[conn.to]?.status === 'offline' || nodeStates[conn.from]?.status === 'offline';
              return (
                <line
                  key={i}
                  x1={from.x} y1={from.y + 3}
                  x2={to.x} y2={to.y - 1}
                  stroke={isOffline ? '#333' : (isDanger ? 'url(#lineGradDanger)' : 'url(#lineGradSafe)')}
                  strokeWidth="0.3"
                  strokeDasharray={isOffline ? '1,1' : 'none'}
                  filter="url(#glow)"
                  style={{ opacity: isOffline ? 0.3 : 0.7 }}
                />
              );
            })}

            {/* Animated packets flowing along connections */}
            {!isUnderAttack && CONNECTIONS.map((conn, i) => {
              const from = getNodePos(conn.from);
              const to = getNodePos(conn.to);
              const isOffline = nodeStates[conn.to]?.status === 'offline' || nodeStates[conn.from]?.status === 'offline';
              if (isOffline) return null;
              return (
                <circle key={`pkt-${i}`} r="0.5" fill="var(--accent-cyan)" filter="url(#glow)">
                  <animateMotion
                    dur={`${2 + i * 0.3}s`}
                    repeatCount="indefinite"
                    path={`M${from.x},${from.y + 3} L${to.x},${to.y - 1}`}
                  />
                </circle>
              );
            })}
          </svg>

          {/* Node boxes overlaid on SVG */}
          {NODES.map((node) => {
            const Icon = node.icon;
            const state = nodeStates[node.id] || {};
            const isSelected = selectedNode === node.id;
            return (
              <motion.div
                key={node.id}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => setSelectedNode(selectedNode === node.id ? null : node.id)}
                style={{
                  position: 'absolute',
                  left: `${node.x}%`,
                  top: `${node.y}%`,
                  transform: 'translate(-50%, -50%)',
                  background: isSelected ? 'rgba(0, 242, 254, 0.1)' : 'rgba(17, 24, 39, 0.9)',
                  border: `1px solid ${isSelected ? 'var(--accent-cyan)' : (state.status === 'offline' ? '#555' : node.color)}`,
                  borderRadius: '12px',
                  padding: '0.6rem 1rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  zIndex: 20,
                  boxShadow: isSelected ? `0 0 20px rgba(0, 242, 254, 0.2)` : `0 0 10px ${node.color}22`,
                  transition: 'all 0.3s ease',
                  opacity: state.status === 'offline' ? 0.5 : 1
                }}
              >
                <div style={{ 
                  width: '8px', height: '8px', borderRadius: '50%', 
                  background: getStatusColor(state.status),
                  boxShadow: `0 0 8px ${getStatusColor(state.status)}`,
                  animation: state.status === 'restarting' ? 'pulse 1s infinite' : 'none'
                }} />
                <Icon size={18} color={state.status === 'offline' ? '#555' : node.color} />
                <span style={{ fontSize: '0.75rem', fontWeight: '600', color: state.status === 'offline' ? '#555' : 'var(--text-primary)', whiteSpace: 'nowrap' }}>
                  {node.label}
                </span>
              </motion.div>
            );
          })}
        </div>

        {/* Right Panel: Node Inspector + Action Log */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Node Inspector */}
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1rem', marginBottom: '1rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Activity size={16} /> Node Inspector
            </h3>
            {selectedNode ? (() => {
              const node = NODES.find(n => n.id === selectedNode);
              const state = nodeStates[selectedNode] || {};
              const Icon = node.icon;
              return (
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
                    <Icon size={28} color={node.color} />
                    <div>
                      <div style={{ fontWeight: '600' }}>{node.label}</div>
                      <div style={{ fontSize: '0.8rem', color: getStatusColor(state.status), display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                        {state.status === 'healthy' && <><CheckCircle2 size={12}/> Healthy</>}
                        {state.status === 'stressed' && <><AlertTriangle size={12}/> Stressed</>}
                        {state.status === 'offline' && <><Power size={12}/> Offline</>}
                        {state.status === 'restarting' && <><RefreshCw size={12}/> Restarting...</>}
                        {state.status === 'active' && <><CheckCircle2 size={12}/> Active</>}
                      </div>
                    </div>
                  </div>

                  {node.id !== 'internet' && (
                    <>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '1.5rem' }}>
                        {[
                          { label: 'CPU', value: state.cpu },
                          { label: 'Memory', value: state.mem },
                          { label: 'Uptime', value: state.uptime },
                          { label: 'Status', value: state.status?.toUpperCase() }
                        ].map((stat, i) => (
                          <div key={i} style={{ background: 'rgba(0,0,0,0.3)', padding: '0.6rem', borderRadius: '8px' }}>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{stat.label}</div>
                            <div style={{ fontSize: '0.95rem', fontWeight: '600', fontFamily: 'var(--font-mono)', marginTop: '0.2rem' }}>{stat.value}</div>
                          </div>
                        ))}
                      </div>

                      {/* Action Buttons */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        {state.status !== 'offline' ? (
                          <>
                            <button onClick={() => handleNodeAction(selectedNode, 'restart')} style={{
                              background: 'rgba(0, 242, 254, 0.1)', border: '1px solid var(--accent-cyan)', color: 'var(--accent-cyan)',
                              padding: '0.6rem', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '0.85rem',
                              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', transition: 'all 0.2s'
                            }}>
                              <RefreshCw size={14} /> Restart Node
                            </button>
                            <button onClick={() => handleNodeAction(selectedNode, 'shutdown')} style={{
                              background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--accent-red)', color: 'var(--accent-red)',
                              padding: '0.6rem', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '0.85rem',
                              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', transition: 'all 0.2s'
                            }}>
                              <Power size={14} /> Shutdown Node
                            </button>
                          </>
                        ) : (
                          <button onClick={() => handleNodeAction(selectedNode, 'poweron')} style={{
                            background: 'rgba(16, 185, 129, 0.1)', border: '1px solid var(--accent-green)', color: 'var(--accent-green)',
                            padding: '0.6rem', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '0.85rem',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', transition: 'all 0.2s'
                          }}>
                            <Power size={14} /> Power On
                          </button>
                        )}
                      </div>
                    </>
                  )}
                </div>
              );
            })() : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '2rem 0' }}>
                Click on a node in the topology map to inspect its status and take actions.
              </p>
            )}
          </div>

          {/* Action Log */}
          <div className="glass-panel" style={{ padding: '1.5rem', flex: 1 }}>
            <h3 style={{ fontSize: '1rem', marginBottom: '1rem', color: 'var(--text-primary)' }}>Action Log</h3>
            <div style={{ 
              background: 'rgba(0,0,0,0.4)', borderRadius: '8px', padding: '0.75rem', 
              fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--accent-green)',
              maxHeight: '200px', overflowY: 'auto'
            }}>
              {actionLog.length === 0 ? (
                <div style={{ color: 'var(--text-muted)' }}>No actions taken yet.</div>
              ) : (
                actionLog.map((log, i) => (
                  <div key={i} style={{ marginBottom: '0.3rem', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '0.3rem' }}>
                    {log}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
