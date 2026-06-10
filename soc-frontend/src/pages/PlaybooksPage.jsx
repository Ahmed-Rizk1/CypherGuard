import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Play, CheckCircle, XCircle, Clock, Terminal, ShieldAlert, Database, Wifi, Server, RotateCcw } from 'lucide-react';

const PLAYBOOKS = [
  {
    id: 'isolate_subnet',
    name: 'Isolate Database Subnet',
    description: 'Immediately isolates the internal database subnet from external traffic to prevent data exfiltration.',
    severity: 'critical',
    icon: Database,
    commands: [
      { cmd: '$ sudo iptables -I FORWARD -d 10.0.2.0/24 -j DROP', delay: 800 },
      { cmd: '[INFO] Rule added to iptables FORWARD chain', delay: 400 },
      { cmd: '$ sudo ip route del 10.0.2.0/24 via 10.0.1.1', delay: 600 },
      { cmd: '[INFO] Route to DB subnet removed', delay: 300 },
      { cmd: '$ ping -c 1 10.0.2.5', delay: 1000 },
      { cmd: 'PING 10.0.2.5 — Request timeout. Network unreachable.', delay: 500 },
      { cmd: '[SUCCESS] ✓ Database subnet 10.0.2.0/24 is now ISOLATED', delay: 0 },
    ]
  },
  {
    id: 'flush_dns',
    name: 'Flush & Reset DNS Cache',
    description: 'Clears all DNS resolver caches across the cluster to eliminate any poisoned DNS records.',
    severity: 'high',
    icon: Wifi,
    commands: [
      { cmd: '$ sudo systemctl stop systemd-resolved', delay: 600 },
      { cmd: '[INFO] DNS resolver service stopped', delay: 300 },
      { cmd: '$ sudo rm -rf /var/cache/bind/*', delay: 500 },
      { cmd: '[INFO] BIND cache directory cleared', delay: 300 },
      { cmd: '$ sudo resolvectl flush-caches', delay: 700 },
      { cmd: '[INFO] System resolver cache flushed', delay: 300 },
      { cmd: '$ sudo systemctl start systemd-resolved', delay: 600 },
      { cmd: '[INFO] DNS resolver service restarted', delay: 300 },
      { cmd: '$ dig google.com +short', delay: 800 },
      { cmd: '142.250.185.14', delay: 200 },
      { cmd: '[SUCCESS] ✓ DNS resolution verified — cache is clean', delay: 0 },
    ]
  },
  {
    id: 'block_c2',
    name: 'Block C2 Communication',
    description: 'Blocks all outbound traffic to known Ransomware Command & Control (C2) servers using threat intelligence feeds.',
    severity: 'critical',
    icon: ShieldAlert,
    commands: [
      { cmd: '$ curl -s https://threatintel.securenet/c2-feed.txt | wc -l', delay: 900 },
      { cmd: '2,847 known C2 IPs loaded from threat feed', delay: 400 },
      { cmd: '$ for ip in $(cat /tmp/c2_list.txt); do iptables -A OUTPUT -d $ip -j DROP; done', delay: 1500 },
      { cmd: '[INFO] Processing 2,847 firewall rules...', delay: 800 },
      { cmd: '[INFO] 2,847 rules applied to OUTPUT chain', delay: 400 },
      { cmd: '$ iptables -L OUTPUT --line-numbers | tail -5', delay: 600 },
      { cmd: '2843  DROP  all  --  anywhere  185.234.72.0/24', delay: 100 },
      { cmd: '2844  DROP  all  --  anywhere  91.219.28.0/24', delay: 100 },
      { cmd: '2845  DROP  all  --  anywhere  45.153.160.0/24', delay: 100 },
      { cmd: '2846  DROP  all  --  anywhere  194.87.68.0/24', delay: 100 },
      { cmd: '2847  DROP  all  --  anywhere  77.83.36.0/24', delay: 100 },
      { cmd: '[SUCCESS] ✓ All known C2 endpoints are now BLOCKED', delay: 0 },
    ]
  },
  {
    id: 'rotate_keys',
    name: 'Emergency Key Rotation',
    description: 'Immediately rotates all API keys, JWT secrets, and database credentials across the infrastructure.',
    severity: 'medium',
    icon: RotateCcw,
    commands: [
      { cmd: '$ openssl rand -hex 64 > /etc/securenet/jwt_secret.key', delay: 500 },
      { cmd: '[INFO] New JWT secret generated (512-bit)', delay: 300 },
      { cmd: '$ securenet-cli db:rotate-password --target=primary', delay: 800 },
      { cmd: '[INFO] PostgreSQL primary password rotated', delay: 400 },
      { cmd: '$ securenet-cli api-keys:regenerate --all', delay: 1000 },
      { cmd: '[INFO] 12 API keys regenerated across 4 services', delay: 400 },
      { cmd: '$ sudo systemctl restart securenet-api securenet-worker', delay: 900 },
      { cmd: '[INFO] Services restarted with new credentials', delay: 400 },
      { cmd: '$ securenet-cli health:check --verbose', delay: 700 },
      { cmd: 'API Gateway ............ OK', delay: 200 },
      { cmd: 'ML Engine .............. OK', delay: 200 },
      { cmd: 'Database ............... OK', delay: 200 },
      { cmd: '[SUCCESS] ✓ All credentials rotated — services healthy', delay: 0 },
    ]
  },
  {
    id: 'snapshot_forensics',
    name: 'Capture Forensic Snapshot',
    description: 'Creates a complete forensic snapshot of system state, memory, and network connections for post-incident analysis.',
    severity: 'medium',
    icon: Server,
    commands: [
      { cmd: '$ mkdir -p /forensics/$(date +%Y%m%d_%H%M%S)', delay: 300 },
      { cmd: '[INFO] Forensics directory created', delay: 200 },
      { cmd: '$ netstat -tunlp > /forensics/active_connections.log', delay: 600 },
      { cmd: '[INFO] 847 active connections captured', delay: 300 },
      { cmd: '$ ps auxf > /forensics/process_tree.log', delay: 500 },
      { cmd: '[INFO] Full process tree dumped', delay: 300 },
      { cmd: '$ cat /proc/meminfo > /forensics/memory_state.log', delay: 400 },
      { cmd: '[INFO] Memory state captured', delay: 300 },
      { cmd: '$ cp /var/log/securenet/*.log /forensics/', delay: 700 },
      { cmd: '[INFO] Application logs archived', delay: 300 },
      { cmd: '$ tar czf /forensics/snapshot_bundle.tar.gz /forensics/*', delay: 1000 },
      { cmd: '[SUCCESS] ✓ Forensic snapshot saved (23.4 MB compressed)', delay: 0 },
    ]
  }
];

export default function PlaybooksPage() {
  const [runningId, setRunningId] = useState(null);
  const [completedIds, setCompletedIds] = useState([]);
  const [terminalLines, setTerminalLines] = useState([]);
  const [currentPlaybook, setCurrentPlaybook] = useState(null);
  const terminalRef = useRef(null);

  // Auto-scroll terminal
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [terminalLines]);

  const runPlaybook = async (playbook) => {
    if (runningId) return; // prevent running multiple
    setRunningId(playbook.id);
    setCurrentPlaybook(playbook);
    setTerminalLines([{ text: `> Executing Playbook: ${playbook.name}`, type: 'header' }, { text: '—'.repeat(50), type: 'divider' }]);

    for (const step of playbook.commands) {
      await new Promise(resolve => setTimeout(resolve, step.delay));
      setTerminalLines(prev => [...prev, { 
        text: step.cmd, 
        type: step.cmd.startsWith('[SUCCESS]') ? 'success' : 
              step.cmd.startsWith('[INFO]') ? 'info' :
              step.cmd.startsWith('$') ? 'command' : 'output'
      }]);
    }

    setRunningId(null);
    setCompletedIds(prev => [...prev, playbook.id]);
  };

  const getSeverityStyle = (severity) => {
    switch(severity) {
      case 'critical': return { bg: 'rgba(239, 68, 68, 0.1)', border: '#ef4444', text: '#ef4444' };
      case 'high': return { bg: 'rgba(249, 115, 22, 0.1)', border: '#f97316', text: '#f97316' };
      case 'medium': return { bg: 'rgba(234, 179, 8, 0.1)', border: '#eab308', text: '#eab308' };
      default: return { bg: 'rgba(255,255,255,0.05)', border: '#555', text: '#aaa' };
    }
  };

  return (
    <div className="dashboard-container">
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>Incident Response Playbooks</h1>
        <p style={{ color: 'var(--text-secondary)' }}>Automated response actions for active threats. Click "Execute" to run a playbook.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
        {PLAYBOOKS.map((pb) => {
          const Icon = pb.icon;
          const isRunning = runningId === pb.id;
          const isCompleted = completedIds.includes(pb.id);
          const sevStyle = getSeverityStyle(pb.severity);

          return (
            <motion.div
              key={pb.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-panel"
              style={{ padding: '1.5rem', position: 'relative', overflow: 'hidden' }}
            >
              <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '3px', background: sevStyle.border }} />

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                  <div style={{ background: sevStyle.bg, padding: '0.6rem', borderRadius: '10px' }}>
                    <Icon size={22} color={sevStyle.text} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: '1rem', marginBottom: '0.2rem' }}>{pb.name}</h3>
                    <span style={{ 
                      fontSize: '0.7rem', fontWeight: '700', textTransform: 'uppercase', 
                      color: sevStyle.text, background: sevStyle.bg, 
                      padding: '0.15rem 0.5rem', borderRadius: '4px', border: `1px solid ${sevStyle.border}` 
                    }}>
                      {pb.severity}
                    </span>
                  </div>
                </div>

                {isCompleted && <CheckCircle size={20} color="var(--accent-green)" />}
              </div>

              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1.25rem', lineHeight: '1.5' }}>
                {pb.description}
              </p>

              <button
                onClick={() => runPlaybook(pb)}
                disabled={isRunning || !!runningId}
                style={{
                  width: '100%',
                  background: isRunning ? 'rgba(0, 242, 254, 0.15)' : (isCompleted ? 'rgba(16, 185, 129, 0.1)' : 'rgba(0, 242, 254, 0.1)'),
                  border: `1px solid ${isRunning ? 'var(--accent-cyan)' : (isCompleted ? 'var(--accent-green)' : 'var(--border-color)')}`,
                  color: isRunning ? 'var(--accent-cyan)' : (isCompleted ? 'var(--accent-green)' : 'var(--text-primary)'),
                  padding: '0.7rem',
                  borderRadius: '8px',
                  cursor: isRunning || !!runningId ? 'not-allowed' : 'pointer',
                  fontWeight: '600',
                  fontSize: '0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                  transition: 'all 0.2s',
                  opacity: (!!runningId && !isRunning) ? 0.5 : 1
                }}
              >
                {isRunning ? <><Clock size={14} /> Executing...</> :
                 isCompleted ? <><CheckCircle size={14} /> Completed — Run Again</> :
                 <><Play size={14} /> Execute Playbook</>}
              </button>
            </motion.div>
          );
        })}
      </div>

      {/* Terminal Output */}
      <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ 
          background: 'rgba(0, 242, 254, 0.05)', padding: '0.75rem 1.25rem', 
          borderBottom: '1px solid var(--border-color)',
          display: 'flex', alignItems: 'center', gap: '0.5rem',
          fontSize: '0.85rem', fontWeight: '600'
        }}>
          <Terminal size={16} color="var(--accent-cyan)" /> 
          Playbook Terminal {currentPlaybook ? `— ${currentPlaybook.name}` : ''}
          {runningId && <span style={{ marginLeft: 'auto', color: 'var(--accent-cyan)', fontSize: '0.75rem', animation: 'pulse 1s infinite' }}>● RUNNING</span>}
        </div>
        <div 
          ref={terminalRef}
          style={{ 
            background: 'rgba(0,0,0,0.6)', 
            padding: '1rem 1.25rem', 
            fontFamily: 'var(--font-mono)', 
            fontSize: '0.8rem',
            minHeight: '200px',
            maxHeight: '350px',
            overflowY: 'auto'
          }}
        >
          {terminalLines.length === 0 ? (
            <div style={{ color: 'var(--text-muted)' }}>
              {'>'} Awaiting playbook execution...<br/>
              {'>'} Select a playbook above and click "Execute" to begin.
            </div>
          ) : (
            terminalLines.map((line, i) => (
              <div key={i} style={{ 
                marginBottom: '0.3rem',
                color: line.type === 'success' ? 'var(--accent-green)' :
                       line.type === 'info' ? 'var(--accent-cyan)' :
                       line.type === 'command' ? '#e2e8f0' :
                       line.type === 'header' ? 'var(--accent-purple)' :
                       line.type === 'divider' ? 'var(--border-color)' :
                       'var(--text-muted)',
                fontWeight: line.type === 'header' || line.type === 'success' ? '700' : '400'
              }}>
                {line.text}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
