/**
 * FeatureGate — Shows an upgrade prompt for gated features.
 */
import { useState } from 'react';

const FEATURE_PLANS = {
  custom_playbooks: 'pro',
  siem_export: 'business',
  api_access: 'pro',
  custom_ml_models: 'enterprise',
  sso: 'enterprise',
};

export default function FeatureGate({ feature, currentPlan = 'free', children }) {
  const [showPrompt, setShowPrompt] = useState(false);
  const requiredPlan = FEATURE_PLANS[feature] || 'pro';

  const planOrder = ['free', 'pro', 'business', 'enterprise'];
  const currentIdx = planOrder.indexOf(currentPlan);
  const requiredIdx = planOrder.indexOf(requiredPlan);

  if (currentIdx >= requiredIdx) {
    return children;
  }

  return (
    <div className="feature-gate-wrapper" style={{ position: 'relative' }}>
      <div
        style={{ filter: 'blur(2px)', pointerEvents: 'none', opacity: 0.5 }}
        aria-hidden="true"
      >
        {children}
      </div>
      <div
        className="feature-gate-overlay"
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'rgba(10, 14, 23, 0.8)',
          borderRadius: '12px',
          backdropFilter: 'blur(4px)',
          cursor: 'pointer',
          zIndex: 10,
        }}
        onClick={() => setShowPrompt(true)}
      >
        <span style={{ fontSize: '32px', marginBottom: '8px' }}>🔒</span>
        <span style={{ color: '#fff', fontWeight: 600, fontSize: '14px' }}>
          Requires {requiredPlan.charAt(0).toUpperCase() + requiredPlan.slice(1)} Plan
        </span>
        <a
          href="/app/billing"
          style={{
            marginTop: '12px',
            padding: '8px 20px',
            background: 'linear-gradient(135deg, #00d4ff, #0090ff)',
            color: '#fff',
            borderRadius: '6px',
            textDecoration: 'none',
            fontSize: '13px',
            fontWeight: 600,
          }}
        >
          Upgrade Now →
        </a>
      </div>
    </div>
  );
}
