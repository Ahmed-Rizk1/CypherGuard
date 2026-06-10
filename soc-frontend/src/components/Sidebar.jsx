import { Shield, LayoutDashboard, Crosshair, Server, Zap, Settings, LogOut, Radio, Users, CreditCard, BarChart3 } from 'lucide-react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/AuthContext';
import RBACGate from './RBACGate';
import NotificationCenter from './NotificationCenter';

export default function Sidebar() {
  const navigate = useNavigate();
  const { logout, user } = useAuth();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <Shield className="logo-icon" size={28} />
        <span className="logo-text">SecureNet SOC</span>
      </div>
      
      <nav className="sidebar-nav">
        <NavLink 
          to="/app/telemetry" 
          className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}
        >
          <LayoutDashboard size={20} />
          <span>Telemetry</span>
        </NavLink>
        
        <NavLink 
          to="/app/threats" 
          className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}
        >
          <Crosshair size={20} />
          <span>Threat Intelligence</span>
        </NavLink>
        
        <NavLink 
          to="/app/nodes" 
          className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}
        >
          <Server size={20} />
          <span>Network Topology</span>
        </NavLink>

        <NavLink 
          to="/app/playbooks" 
          className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}
        >
          <Zap size={20} />
          <span>Response Playbooks</span>
        </NavLink>

        {/* SaaS Navigation */}
        <div style={{ height: '1px', background: '#1e2a3a', margin: '12px 0' }} />

        <NavLink 
          to="/app/sensors" 
          className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}
        >
          <Radio size={20} />
          <span>Sensors</span>
        </NavLink>

        <NavLink 
          to="/app/reports" 
          className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}
        >
          <BarChart3 size={20} />
          <span>Reports</span>
        </NavLink>

        <RBACGate minRole="admin">
          <NavLink 
            to="/app/team" 
            className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}
          >
            <Users size={20} />
            <span>Team</span>
          </NavLink>
        </RBACGate>

        <RBACGate minRole="owner">
          <NavLink 
            to="/app/billing" 
            className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}
          >
            <CreditCard size={20} />
            <span>Billing</span>
          </NavLink>
        </RBACGate>
      </nav>

      <div className="sidebar-nav" style={{ flex: 0, marginTop: 'auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 8px' }}>
          <NotificationCenter />
          {user && (
            <span style={{ color: '#6b7280', fontSize: '11px', maxWidth: '100px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {user.email}
            </span>
          )}
        </div>
        <NavLink 
          to="/app/settings" 
          className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}
        >
          <Settings size={20} />
          <span>Settings</span>
        </NavLink>
        <div 
          className="nav-item" 
          onClick={handleLogout}
          style={{ color: 'var(--accent-red)', marginTop: '0.5rem', cursor: 'pointer' }}
        >
          <LogOut size={20} />
          <span>Logout Session</span>
        </div>
      </div>
    </aside>
  );
}
