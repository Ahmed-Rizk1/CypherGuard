import { useEffect, useState, useRef } from 'react';
import { Terminal } from 'lucide-react';

export default function RawTerminal() {
  const [logs, setLogs] = useState([]);
  const terminalRef = useRef(null);

  // Generate random packet data to simulate raw stream
  useEffect(() => {
    const protocols = ['TCP', 'UDP', 'ICMP', 'HTTP'];
    const ports = [80, 443, 22, 53, 3306, 8080];
    
    const generatePacket = () => {
      const srcIP = `${Math.floor(Math.random()*255)}.${Math.floor(Math.random()*255)}.${Math.floor(Math.random()*255)}.${Math.floor(Math.random()*255)}`;
      const dstIP = `192.168.1.${Math.floor(Math.random()*255)}`;
      const proto = protocols[Math.floor(Math.random() * protocols.length)];
      const port = ports[Math.floor(Math.random() * ports.length)];
      const size = Math.floor(Math.random() * 1500) + 40;
      
      return `[${new Date().toISOString()}] CAPTURE: SRC=${srcIP} DST=${dstIP} PROTO=${proto} DPORT=${port} LEN=${size} TTL=${Math.floor(Math.random()*64)+64} FLAGS=0x${Math.floor(Math.random()*16).toString(16)}...`;
    };

    const interval = setInterval(() => {
      setLogs(prev => {
        const newLogs = [...prev, generatePacket()];
        // Keep only last 50 logs to prevent memory leaks
        if (newLogs.length > 50) return newLogs.slice(newLogs.length - 50);
        return newLogs;
      });
    }, 150); // Fast stream

    return () => clearInterval(interval);
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="glass-panel" style={{ padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div style={{ 
        background: 'rgba(0,0,0,0.8)', 
        padding: '0.5rem 1rem', 
        borderBottom: '1px solid var(--border-color)',
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        color: '#10B981',
        fontSize: '0.8rem',
        fontWeight: 'bold',
        textTransform: 'uppercase'
      }}>
        <Terminal size={14} /> RAW PACKET STREAM (wlan0)
      </div>
      <div 
        ref={terminalRef}
        style={{
          background: '#050505',
          color: '#10B981',
          padding: '1rem',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.75rem',
          height: '250px',
          overflowY: 'auto',
          lineHeight: '1.4',
          opacity: 0.8
        }}
      >
        {logs.map((log, idx) => (
          <div key={idx} style={{ opacity: 1 - ((logs.length - idx) * 0.02) }}>
            {log}
          </div>
        ))}
      </div>
    </div>
  );
}
