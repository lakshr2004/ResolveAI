
import {
  createContext,
  useContext,
  useEffect,
  useState,
} from 'react';

import api from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const storedUser = sessionStorage.getItem('resolveai_user');
      return storedUser ? JSON.parse(storedUser) : null;
    } catch {
      sessionStorage.removeItem('resolveai_user');
      return null;
    }
  });

  const [token, setToken] = useState(
    () => sessionStorage.getItem('resolveai_token')
  );

  const [loading, setLoading] = useState(false);

  const logout = () => {
    sessionStorage.removeItem('resolveai_token');
    sessionStorage.removeItem('resolveai_user');

    setToken(null);
    setUser(null);
  };

  useEffect(() => {
    const handleUnauthorized = () => {
      logout();
    };

    window.addEventListener(
      'resolveai:unauthorized',
      handleUnauthorized
    );

    return () => {
      window.removeEventListener(
        'resolveai:unauthorized',
        handleUnauthorized
      );
    };
  }, []);

  const login = async (email, password) => {
    setLoading(true);

    try {
      const response = await api.post('/api/auth/login', {
        email,
        password,
      });

      const {
        access_token,
        user: loggedInUser,
      } = response.data;

      sessionStorage.setItem(
        'resolveai_token',
        access_token
      );

      sessionStorage.setItem(
        'resolveai_user',
        JSON.stringify(loggedInUser)
      );

      setToken(access_token);
      setUser(loggedInUser);

      return loggedInUser;
    } finally {
      setLoading(false);
    }
  };

  const value = {
    user,
    token,
    loading,
    isAuthenticated: Boolean(token && user),
    login,
    logout,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      'useAuth must be used within AuthProvider'
    );
  }

  return context;
}
