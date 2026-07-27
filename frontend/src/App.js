import React, { useEffect, useState } from 'react';
import AuthPage from './components/AuthPage';
import Dashboard from './components/Dashboard';
import { API_BASE_URL } from './config';

const AUTH_TOKEN_KEY = 'algorise_auth_token';
const AUTH_USER_KEY = 'algorise_auth_user';

function App() {
  const [authState, setAuthState] = useState({
    loading: true,
    token: null,
    user: null,
  });

  useEffect(() => {
    let isActive = true;

    const restoreSession = async () => {
      const storedToken = localStorage.getItem(AUTH_TOKEN_KEY);

      if (!storedToken) {
        if (isActive) {
          setAuthState({ loading: false, token: null, user: null });
        }
        return;
      }

      try {
        const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
          headers: {
            Authorization: `Bearer ${storedToken}`,
          },
        });

        if (!response.ok) {
          throw new Error('Session expired');
        }

        const user = await response.json();

        if (!isActive) {
          return;
        }

        localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
        setAuthState({ loading: false, token: storedToken, user });
      } catch (error) {
        localStorage.removeItem(AUTH_TOKEN_KEY);
        localStorage.removeItem(AUTH_USER_KEY);

        if (isActive) {
          setAuthState({ loading: false, token: null, user: null });
        }
      }
    };

    restoreSession();

    return () => {
      isActive = false;
    };
  }, []);

  const handleAuthSuccess = ({ access_token, user }) => {
    localStorage.setItem(AUTH_TOKEN_KEY, access_token);
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
    setAuthState({ loading: false, token: access_token, user });
  };

  const handleLogout = () => {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
    setAuthState({ loading: false, token: null, user: null });
  };

  if (authState.loading) {
    return (
      <div className="app-container auth-loading-screen">
        <div className="glass-panel auth-loading-card">
          <div className="spinner"></div>
          <h2 className="auth-loading-title">Verifying your session</h2>
          <p className="auth-loading-copy">Connecting to your Algorise workspace...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      {authState.token ? (
        <Dashboard
          user={authState.user}
          token={authState.token}
          onLogout={handleLogout}
        />
      ) : (
        <AuthPage onAuthSuccess={handleAuthSuccess} />
      )}
    </div>
  );
}

export default App;
