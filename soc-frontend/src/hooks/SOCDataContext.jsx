/**
 * SOCDataContext — Shared WebSocket context provider.
 *
 * Lifts the WebSocket connection to the AppLayout level so all child pages
 * share a single connection instead of creating one per page mount.
 * Requires authentication — passes the JWT token as a query parameter.
 */
import { createContext, useContext } from 'react';
import { useSOCData } from './useSOCData';
import { useAuth } from './AuthContext';

const SOCDataContext = createContext(null);

export function SOCDataProvider({ children }) {
  const { token } = useAuth();
  const socData = useSOCData(token);

  return (
    <SOCDataContext.Provider value={socData}>
      {children}
    </SOCDataContext.Provider>
  );
}

export function useSOCDataContext() {
  const context = useContext(SOCDataContext);
  if (!context) {
    throw new Error('useSOCDataContext must be used within a SOCDataProvider');
  }
  return context;
}
