/**
 * BillingPage — Subscription and usage management.
 */
import { useState, useEffect } from 'react';
import { useAuth } from '../hooks/AuthContext';
import axios from 'axios';

const PLANS = [
  {
    id: 'free', name: 'Free', price: '$0', period: 'forever',
    features: ['1 Sensor', '1 User', '50 AI Analyses/mo', '7-day retention'],
    color: '#6b7280',
  },
  {
    id: 'pro', name: 'Pro', price: '$49', period: '/month',
    features: ['5 Sensors', '5 Users', '500 AI Analyses/mo', '30-day retention', 'Custom Playbooks', 'API Access'],
    color: '#00d4ff', popular: true,
  },
  {
    id: 'business', name: 'Business', price: '$199', period: '/month',
    features: ['25 Sensors', '25 Users', '5,000 AI Analyses/mo', '90-day retention', 'SIEM Export', 'Priority Support'],
    color: '#8b5cf6',
  },
  {
    id: 'enterprise', name: 'Enterprise', price: 'Custom', period: '',
    features: ['Unlimited Sensors', 'Unlimited Users', 'Unlimited AI', '1-year retention', 'SSO/SAML', 'MSSP Mode'],
    color: '#f59e0b',
  },
];

export default function BillingPage() {
  const { token } = useAuth();
  const [usage, setUsage] = useState(null);
  const [loading, setLoading] = useState(true);

  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    const fetchUsage = async () => {
      try {
        const res = await axios.get('/v1/api/billing/usage', { headers });
        setUsage(res.data?.data);
      } catch { /* ignore */ }
      setLoading(false);
    };
    fetchUsage();
  }, []);

  const UsageBar = ({ label, used, max }) => {
    const pct = max === -1 ? 0 : Math.min((used / max) * 100, 100);
    const isUnlimited = max === -1;
    return (
      <div style={{ marginBottom: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '13px' }}>
          <span style={{ color: '#9ca3af' }}>{label}</span>
          <span style={{ color: '#fff', fontWeight: 500 }}>
            {used} / {isUnlimited ? '∞' : max}
          </span>
        </div>
        <div style={{ height: '6px', background: '#1e2a3a', borderRadius: '3px', overflow: 'hidden' }}>
          <div style={{
            height: '100%',
            width: `${isUnlimited ? 0 : pct}%`,
            background: pct > 80 ? '#ef4444' : pct > 60 ? '#f59e0b' : '#00d4ff',
            borderRadius: '3px',
            transition: 'width 0.3s',
          }} />
        </div>
      </div>
    );
  };

  return (
    <div className="page-content">
      <h1 style={{ color: '#fff', fontSize: '22px', marginBottom: '24px' }}>💳 Billing & Plans</h1>

      {/* Current Usage */}
      {usage && (
        <div className="card" style={{ marginBottom: '32px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
            <h3 style={{ color: '#fff', margin: 0 }}>Current Usage</h3>
            <span style={{
              padding: '3px 12px',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 600,
              textTransform: 'uppercase',
              color: '#00d4ff',
              background: '#00d4ff15',
            }}>
              {usage.plan} plan
            </span>
            {usage.status === 'trial' && (
              <span style={{
                padding: '3px 12px',
                borderRadius: '4px',
                fontSize: '12px',
                color: '#f59e0b',
                background: '#f59e0b15',
              }}>
                Trial ends {usage.trial_ends_at ? new Date(usage.trial_ends_at).toLocaleDateString() : 'soon'}
              </span>
            )}
          </div>
          <UsageBar label="Sensors" used={usage.sensors?.used || 0} max={usage.sensors?.max || 1} />
          <UsageBar label="Team Members" used={usage.users?.used || 0} max={usage.users?.max || 1} />
          <UsageBar label="AI Analyses (monthly)" used={usage.ai_analyses?.used || 0} max={usage.ai_analyses?.max || 50} />
        </div>
      )}

      {/* Plan Comparison */}
      <h3 style={{ color: '#9ca3af', fontSize: '13px', textTransform: 'uppercase', marginBottom: '16px' }}>Available Plans</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
        {PLANS.map(plan => (
          <div
            key={plan.id}
            className="card"
            style={{
              border: usage?.plan === plan.id ? `2px solid ${plan.color}` : '1px solid #1e2a3a',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            {plan.popular && (
              <div style={{
                position: 'absolute',
                top: '12px',
                right: '-28px',
                transform: 'rotate(45deg)',
                background: plan.color,
                color: '#fff',
                fontSize: '10px',
                fontWeight: 700,
                padding: '2px 32px',
              }}>
                POPULAR
              </div>
            )}
            <h3 style={{ color: plan.color, fontSize: '18px', marginBottom: '4px' }}>{plan.name}</h3>
            <div style={{ marginBottom: '16px' }}>
              <span style={{ fontSize: '32px', fontWeight: 700, color: '#fff' }}>{plan.price}</span>
              <span style={{ color: '#6b7280', fontSize: '14px' }}>{plan.period}</span>
            </div>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {plan.features.map((f, i) => (
                <li key={i} style={{ color: '#9ca3af', fontSize: '13px', padding: '4px 0' }}>
                  ✓ {f}
                </li>
              ))}
            </ul>
            {usage?.plan !== plan.id && plan.id !== 'free' && (
              <button
                style={{
                  marginTop: '16px',
                  width: '100%',
                  padding: '10px',
                  background: plan.popular ? `linear-gradient(135deg, ${plan.color}, ${plan.color}cc)` : 'transparent',
                  border: plan.popular ? 'none' : `1px solid ${plan.color}`,
                  color: '#fff',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontWeight: 600,
                  fontSize: '13px',
                }}
              >
                {plan.id === 'enterprise' ? 'Contact Sales' : 'Upgrade'}
              </button>
            )}
            {usage?.plan === plan.id && (
              <div style={{
                marginTop: '16px',
                textAlign: 'center',
                color: plan.color,
                fontWeight: 600,
                fontSize: '13px',
              }}>
                ✓ Current Plan
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
