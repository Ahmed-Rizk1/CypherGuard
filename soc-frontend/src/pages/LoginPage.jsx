import { motion, AnimatePresence } from 'framer-motion';
import { Link, useNavigate } from 'react-router-dom';
import { Shield, Fingerprint, Lock, ArrowRight, ScanLine, CheckCircle } from 'lucide-react';
import { useState, useEffect } from 'react';
import { useAuth } from '../hooks/AuthContext';

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, isLoading, error } = useAuth();
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  
  // Steps: 'credentials' -> 'authenticating' -> 'granted'
  const [step, setStep] = useState('credentials');
  const [scanProgress, setScanProgress] = useState(0);

  // Authentication transition animation
  useEffect(() => {
    if (step !== 'authenticating') return;
    const interval = setInterval(() => {
      setScanProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setTimeout(() => {
            setStep('granted');
            setTimeout(() => navigate('/app/telemetry'), 1200);
          }, 400);
          return 100;
        }
        return prev + 2;
      });
    }, 40);
    return () => clearInterval(interval);
  }, [step, navigate]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError('');
    
    if (!email || !password) {
      setLoginError('Please enter both email and password.');
      return;
    }

    const success = await login(email, password);
    if (success) {
      setStep('authenticating');
      setScanProgress(0);
    } else {
      setLoginError('Invalid credentials. Please try again.');
    }
  };

  return (
    <div style={{ 
      backgroundColor: 'var(--bg-base)', 
      minHeight: '100vh', 
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '2rem',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Background gradients */}
      <div style={{ position: 'absolute', top: '10%', left: '20%', width: '40vw', height: '40vw', background: 'radial-gradient(circle, var(--accent-cyan-dim) 0%, transparent 70%)', filter: 'blur(60px)', zIndex: 0 }} />
      <div style={{ position: 'absolute', bottom: '10%', right: '20%', width: '40vw', height: '40vw', background: 'radial-gradient(circle, var(--accent-purple-dim) 0%, transparent 70%)', filter: 'blur(60px)', zIndex: 0 }} />

      <AnimatePresence mode="wait">
        {/* STEP 1: Credentials */}
        {step === 'credentials' && (
          <motion.div 
            key="credentials"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ duration: 0.4 }}
            style={{
              background: 'rgba(17, 24, 39, 0.7)',
              backdropFilter: 'blur(20px)',
              border: '1px solid var(--border-highlight)',
              padding: '3rem',
              borderRadius: '24px',
              width: '100%',
              maxWidth: '480px',
              position: 'relative',
              zIndex: 10,
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)'
            }}
          >
            <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
              <Shield size={48} color="var(--accent-cyan)" style={{ margin: '0 auto 1rem', filter: 'drop-shadow(0 0 10px rgba(0, 242, 254, 0.5))' }} />
              <h2 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>Operator Login</h2>
              <p style={{ color: 'var(--text-secondary)' }}>Authenticate to access SOC controls.</p>
            </div>

            <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {loginError && (
                <div style={{ color: 'var(--accent-red)', fontSize: '0.9rem', textAlign: 'center', background: 'rgba(239, 68, 68, 0.1)', padding: '0.5rem', borderRadius: '8px', border: '1px solid var(--accent-red)' }}>
                  {loginError}
                </div>
              )}
              {error && !loginError && (
                <div style={{ color: 'var(--accent-red)', fontSize: '0.9rem', textAlign: 'center', background: 'rgba(239, 68, 68, 0.1)', padding: '0.5rem', borderRadius: '8px', border: '1px solid var(--accent-red)' }}>
                  {error}
                </div>
              )}
              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.9rem', fontWeight: '500' }}>Operator ID</label>
                <div style={{ position: 'relative' }}>
                  <Fingerprint size={20} color="var(--text-muted)" style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)' }} />
                  <input 
                    type="text" 
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="admin@securenet.local"
                    style={{
                      width: '100%',
                      background: 'rgba(0,0,0,0.3)',
                      border: '1px solid var(--border-color)',
                      color: 'white',
                      padding: '1rem 1rem 1rem 3rem',
                      borderRadius: '8px',
                      fontSize: '1rem',
                      outline: 'none',
                      transition: 'border-color 0.2s'
                    }} 
                    onFocus={(e) => e.target.style.borderColor = 'var(--accent-cyan)'}
                    onBlur={(e) => e.target.style.borderColor = 'var(--border-color)'}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.9rem', fontWeight: '500' }}>Passkey</label>
                <div style={{ position: 'relative' }}>
                  <Lock size={20} color="var(--text-muted)" style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)' }} />
                  <input 
                    type="password" 
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter passkey..."
                    style={{
                      width: '100%',
                      background: 'rgba(0,0,0,0.3)',
                      border: '1px solid var(--border-color)',
                      color: 'white',
                      padding: '1rem 1rem 1rem 3rem',
                      borderRadius: '8px',
                      fontSize: '1rem',
                      outline: 'none',
                      transition: 'border-color 0.2s'
                    }} 
                    onFocus={(e) => e.target.style.borderColor = 'var(--accent-cyan)'}
                    onBlur={(e) => e.target.style.borderColor = 'var(--border-color)'}
                  />
                </div>
              </div>

              <button 
                type="submit" 
                disabled={isLoading}
                style={{
                  background: 'var(--accent-cyan)',
                  color: '#000',
                  border: 'none',
                  padding: '1rem',
                  borderRadius: '8px',
                  fontSize: '1rem',
                  fontWeight: '700',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                  marginTop: '1rem',
                  transition: 'all 0.2s',
                  boxShadow: '0 0 20px rgba(0, 242, 254, 0.3)'
                }}
              >
                Initialize Session <ArrowRight size={20} />
              </button>
            </form>

            <div style={{ textAlign: 'center', marginTop: '2rem' }}>
              <Link to="/" style={{ color: 'var(--text-muted)', fontSize: '0.9rem', textDecoration: 'underline' }}>
                Return to Public Portal
              </Link>
            </div>
          </motion.div>
        )}

        {/* STEP 2: Authentication Transition */}
        {step === 'authenticating' && (
          <motion.div
            key="authenticating"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.1 }}
            transition={{ duration: 0.5 }}
            style={{
              background: 'rgba(17, 24, 39, 0.7)',
              backdropFilter: 'blur(20px)',
              border: '1px solid var(--accent-cyan)',
              padding: '3rem',
              borderRadius: '24px',
              width: '100%',
              maxWidth: '480px',
              position: 'relative',
              zIndex: 10,
              boxShadow: '0 0 60px rgba(0, 242, 254, 0.15)',
              textAlign: 'center'
            }}
          >
            <ScanLine size={64} color="var(--accent-cyan)" style={{ margin: '0 auto 1.5rem', filter: 'drop-shadow(0 0 15px rgba(0, 242, 254, 0.6))' }} />
            <h2 style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>Establishing Secure Session</h2>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>Initializing encrypted channel...</p>
            
            {/* Progress bar */}
            <div style={{ background: 'rgba(0,0,0,0.4)', borderRadius: '999px', height: '8px', overflow: 'hidden', marginBottom: '1rem' }}>
              <motion.div 
                initial={{ width: '0%' }}
                animate={{ width: `${scanProgress}%` }}
                style={{ 
                  height: '100%', 
                  background: 'linear-gradient(90deg, var(--accent-cyan), var(--accent-purple))',
                  borderRadius: '999px',
                  boxShadow: '0 0 15px rgba(0, 242, 254, 0.5)'
                }}
              />
            </div>
            <p style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)', fontSize: '0.9rem' }}>
              {scanProgress}% — {scanProgress < 100 ? 'Initializing secure session...' : 'SESSION ESTABLISHED'}
            </p>
          </motion.div>
        )}

        {/* STEP 3: Access Granted */}
        {step === 'granted' && (
          <motion.div
            key="granted"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6, type: 'spring' }}
            style={{
              textAlign: 'center',
              position: 'relative',
              zIndex: 10
            }}
          >
            <motion.div
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ duration: 0.8 }}
            >
              <CheckCircle size={96} color="var(--accent-green)" style={{ filter: 'drop-shadow(0 0 30px rgba(16, 185, 129, 0.5))' }} />
            </motion.div>
            <h2 style={{ fontSize: '2rem', marginTop: '1.5rem', color: 'var(--accent-green)' }}>ACCESS GRANTED</h2>
            <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem', fontFamily: 'var(--font-mono)' }}>
              Redirecting to SOC Command Center...
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
