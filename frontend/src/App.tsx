import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useEffect } from 'react';
import { AuthPage } from '@/pages/AuthPage';
import { LobbyPage } from '@/pages/LobbyPage';
import { TablePage } from '@/pages/TablePage';
import { ToastContainer } from '@/components/common/Toast';
import { useAuthStore } from '@/stores/authStore';

function App() {
  const { fetchUser, isAuthenticated, isLoading } = useAuthStore();

  // Check auth on mount
  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  // Show loading while checking auth
  if (isLoading) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <div className="text-center">
          <span className="text-6xl animate-bounce">🃏</span>
          <p className="mt-4 text-text-muted">로딩 중...</p>
        </div>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/auth/login" element={<AuthPage />} />
        <Route path="/auth/register" element={<AuthPage />} />

        {/* Protected routes */}
        <Route
          path="/lobby"
          element={isAuthenticated ? <LobbyPage /> : <Navigate to="/auth/login" />}
        />
        <Route
          path="/table/:tableId"
          element={isAuthenticated ? <TablePage /> : <Navigate to="/auth/login" />}
        />

        {/* Default redirect */}
        <Route
          path="/"
          element={<Navigate to={isAuthenticated ? '/lobby' : '/auth/login'} />}
        />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
      <ToastContainer />
    </BrowserRouter>
  );
}

export default App;
