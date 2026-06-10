import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './hooks/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import EmailVerifyPage from './pages/EmailVerifyPage';
import OnboardingWizard from './pages/OnboardingWizard';
import AppLayout from './components/AppLayout';
import Telemetry from './pages/Telemetry';
import Threats from './pages/Threats';
import SystemNodes from './pages/SystemNodes';
import PlaybooksPage from './pages/PlaybooksPage';
import SettingsPage from './pages/SettingsPage';
import SensorsPage from './pages/SensorsPage';
import TeamPage from './pages/TeamPage';
import BillingPage from './pages/BillingPage';
import ReportsPage from './pages/ReportsPage';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Routes */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/verify" element={<EmailVerifyPage />} />
          
          {/* Onboarding — Protected but outside main layout */}
          <Route path="/app/onboarding" element={
            <ProtectedRoute>
              <OnboardingWizard />
            </ProtectedRoute>
          } />

          {/* Dashboard Routes — Protected */}
          <Route path="/app" element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }>
            {/* Redirect /app to /app/telemetry by default */}
            <Route index element={<Navigate to="/app/telemetry" replace />} />
            <Route path="telemetry" element={<Telemetry />} />
            <Route path="threats" element={<Threats />} />
            <Route path="nodes" element={<SystemNodes />} />
            <Route path="playbooks" element={<PlaybooksPage />} />
            <Route path="settings" element={<SettingsPage />} />
            {/* SaaS Routes */}
            <Route path="sensors" element={<SensorsPage />} />
            <Route path="team" element={<TeamPage />} />
            <Route path="billing" element={<BillingPage />} />
            <Route path="reports" element={<ReportsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
