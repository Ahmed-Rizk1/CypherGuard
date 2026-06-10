/**
 * SignupPage — New tenant registration form.
 */
import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../hooks/AuthContext';

export default function SignupPage() {
  const { signup, isLoading, error } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ companyName: '', fullName: '', email: '', password: '' });
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const result = await signup(form.companyName, form.fullName, form.email, form.password);
    if (result.success) {
      setSuccess(true);
    }
  };

  if (success) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <div style={{ textAlign: 'center' }}>
            <span style={{ fontSize: '48px' }}>📧</span>
            <h2 style={{ margin: '16px 0 8px', color: '#fff' }}>Check Your Email</h2>
            <p style={{ color: '#9ca3af', lineHeight: 1.6 }}>
              We sent a verification link to <strong style={{ color: '#00d4ff' }}>{form.email}</strong>.
              <br />Click it to activate your account.
            </p>
            <Link to="/login" className="auth-link" style={{ marginTop: '24px', display: 'inline-block' }}>
              ← Back to Login
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <span style={{ fontSize: '36px' }}>🛡️</span>
          <h1 style={{ margin: '8px 0 4px', fontSize: '22px', color: '#fff' }}>Create Your SOC</h1>
          <p style={{ color: '#6b7280', fontSize: '14px' }}>14-day free trial • No credit card required</p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="companyName">Company Name</label>
            <input
              id="companyName"
              type="text"
              required
              placeholder="Acme Corp"
              value={form.companyName}
              onChange={e => setForm({ ...form, companyName: e.target.value })}
              className="form-input"
            />
          </div>
          <div className="form-group">
            <label htmlFor="fullName">Your Full Name</label>
            <input
              id="fullName"
              type="text"
              required
              placeholder="Jane Doe"
              value={form.fullName}
              onChange={e => setForm({ ...form, fullName: e.target.value })}
              className="form-input"
            />
          </div>
          <div className="form-group">
            <label htmlFor="signupEmail">Work Email</label>
            <input
              id="signupEmail"
              type="email"
              required
              placeholder="jane@acme.com"
              value={form.email}
              onChange={e => setForm({ ...form, email: e.target.value })}
              className="form-input"
            />
          </div>
          <div className="form-group">
            <label htmlFor="signupPassword">Password</label>
            <input
              id="signupPassword"
              type="password"
              required
              minLength={8}
              placeholder="Min 8 characters"
              value={form.password}
              onChange={e => setForm({ ...form, password: e.target.value })}
              className="form-input"
            />
          </div>

          {error && <div className="form-error">{error}</div>}

          <button type="submit" className="btn-primary" disabled={isLoading} style={{ width: '100%', marginTop: '8px' }}>
            {isLoading ? 'Creating...' : 'Start Free Trial →'}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: '20px', fontSize: '13px', color: '#6b7280' }}>
          Already have an account? <Link to="/login" className="auth-link">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
