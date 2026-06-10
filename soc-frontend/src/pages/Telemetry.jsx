import { useSOCDataContext } from '../hooks/SOCDataContext';
import MetricsGrid from '../components/MetricsGrid';
import TrafficChart from '../components/TrafficChart';
import FirewallPanel from '../components/FirewallPanel';
import ThreatLog from '../components/ThreatLog';
import RawTerminal from '../components/RawTerminal';
import LiveAlertsWidget from '../components/LiveAlertsWidget';
import '../App.css';

export default function Telemetry() {
  const { metrics, history, blockedIps, alerts } = useSOCDataContext();

  return (
    <div className="dashboard-container">
      <MetricsGrid metrics={metrics} blockedCount={blockedIps.length} />

      <div className="charts-grid">
        <TrafficChart
          data={history}
          dataKey="packets"
          title="NETWORK PACKET VELOCITY"
          color="var(--accent-cyan)"
          gradientId="colorPkts"
          icon="Activity"
        />
        <TrafficChart
          data={history}
          dataKey="bytes"
          title="BANDWIDTH CONSUMPTION"
          color="var(--accent-purple)"
          gradientId="colorBytes"
          yFormatter={(val) => `${(val / 1024).toFixed(0)}kb`}
          icon="Zap"
        />
      </div>

      <div className="lower-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
        <FirewallPanel blockedIps={blockedIps} />
        <ThreatLog alerts={alerts} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
        <RawTerminal />
        <LiveAlertsWidget />
      </div>
    </div>
  );
}
