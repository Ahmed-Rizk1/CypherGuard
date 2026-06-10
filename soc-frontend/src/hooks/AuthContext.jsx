/**
 * AuthContext — JWT authentication state for the SecureNet SaaS app.
 *
 * Stores JWT in sessionStorage. Decodes the `tid` (tenant_id) claim.
 * Provides login, signup, logout functions and auth state to child components.
 */
import { createContext, useContext, useState, useCallback, useMemo } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

// --- JWT decoder (no library dependency) ---
function parseJwt(token) {
  try {
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(atob(base64));
    return payload;
  } catch {
    return {};
  }
}

// Safe sessionStorage helpers
function getStoredAuth() {
  try {
    const token = sessionStorage.getItem('securenet_token');
    const refreshToken = sessionStorage.getItem('securenet_refresh');
    const userStr = sessionStorage.getItem('securenet_user');
    if (token && userStr) {
      return { token, refreshToken, user: JSON.parse(userStr) };
    }
  } catch { /* ignore parse errors */ }
  return { token: null, refreshToken: null, user: null };
}

function setStoredAuth(token, refreshToken, user) {
  try {
    if (token && user) {
      sessionStorage.setItem('securenet_token', token);
      sessionStorage.setItem('securenet_user', JSON.stringify(user));
      if (refreshToken) {
        sessionStorage.setItem('securenet_refresh', refreshToken);
      }
    } else {
      sessionStorage.removeItem('securenet_token');
      sessionStorage.removeItem('securenet_refresh');
      sessionStorage.removeItem('securenet_user');
    }
  } catch { /* ignore storage errors */ }
}

export function AuthProvider({ children }) {
  const stored = getStoredAuth();
  const [token, setToken] = useState(stored.token);
  const [refreshToken, setRefreshToken] = useState(stored.refreshToken);
  const [user, setUser] = useState(stored.user);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const login = useCallback(async (email, password) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await axios.post('/v1/auth/login', { email, password });
      const { access_token, refresh_token, role } = res.data;
      const claims = parseJwt(access_token);
      const userData = {
        email,
        role,
        tenant_id: claims.tid || '',
        user_id: claims.sub || '',
      };
      setToken(access_token);
      setRefreshToken(refresh_token);
      setUser(userData);
      setStoredAuth(access_token, refresh_token, userData);
      return true;
    } catch (err) {
      const msg = err.response?.data?.detail || 'Login failed';
      setError(msg);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const signup = useCallback(async (companyName, fullName, email, password) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await axios.post('/v1/auth/signup', {
        company_name: companyName,
        full_name: fullName,
        email,
        password,
      });
      return { success: true, data: res.data };
    } catch (err) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || 'Signup failed';
      setError(msg);
      return { success: false, error: msg };
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    // Call backend logout to blacklist token
    try {
      if (token) {
        await axios.post('/v1/auth/logout', null, {
          headers: { Authorization: `Bearer ${token}` },
        });
      }
    } catch { /* ignore */ }
    setToken(null);
    setRefreshToken(null);
    setUser(null);
    setError(null);
    setStoredAuth(null, null, null);
  }, [token]);

  const isAuthenticated = !!token;

  const value = useMemo(() => ({
    token,
    refreshToken,
    user,
    isAuthenticated,
    isLoading,
    error,
    login,
    signup,
    logout,
    setError,
  }), [token, refreshToken, user, isAuthenticated, isLoading, error, login, signup, logout]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default AuthContext;
