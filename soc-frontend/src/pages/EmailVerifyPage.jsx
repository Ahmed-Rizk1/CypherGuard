/**
 * EmailVerifyPage — Handles email verification token from URL.
 */
import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import axios from 'axios';

export default function EmailVerifyPage() {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState('verifying'); // verifying | success | error
  const [message, setMessage] = useState('');
  const token = searchParams.get('token');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('Missing verification token.');
      return;
    }

    const verify = async () => {
      try {
        const res = await axios.post('/v1/auth/verify-email', { token });
        setStatus('success');
        setMessage(res.data?.message || 'Email verified!');
      } catch (err) {
        setStatus('error');
        setMessage(err.response?.data?.error?.message || 'Verification failed. The link may have expired.');
      }
    };
    verify();
  }, [token]);

  return (
    <div className="auth-page">
      <div className="auth-card" style={{ textAlign: 'center' }}>
        {status === 'verifying' && (
          <>
            <div className="spinner" style={{ margin: '0 auto 20px' }} />
            <h2 style={{ color: '#fff' }}>Verifying your email...</h2>
          </>
        )}
        {status === 'success' && (
          <>
            <span style={{ fontSize: '48px' }}>✅</span>
            <h2 style={{ margin: '16px 0 8px', color: '#fff' }}>Email Verified!</h2>
            <p style={{ color: '#9ca3af' }}>{message}</p>
            <Link to="/login" className="btn-primary" style={{ display: 'inline-block', marginTop: '20px' }}>
              Continue to Login →
            </Link>
          </>
        )}
        {status === 'error' && (
          <>
            <span style={{ fontSize: '48px' }}>❌</span>
            <h2 style={{ margin: '16px 0 8px', color: '#fff' }}>Verification Failed</h2>
            <p style={{ color: '#ef4444' }}>{message}</p>
            <Link to="/login" className="auth-link" style={{ display: 'inline-block', marginTop: '16px' }}>
              ← Back to Login
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
