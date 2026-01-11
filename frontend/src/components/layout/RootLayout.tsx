import type { ReactNode } from 'react';
import { Header } from './Header';
import { ConnectionBanner } from './ConnectionBanner';
import { ToastContainer } from '@/components/common/Toast';

interface RootLayoutProps {
  children: ReactNode;
  title?: string;
  subtitle?: string;
}

export function RootLayout({ children, title, subtitle }: RootLayoutProps) {
  return (
    <div className="min-h-screen flex flex-col">
      <Header title={title} subtitle={subtitle} />
      <ConnectionBanner />
      <main className="flex-1">{children}</main>
      <ToastContainer />
    </div>
  );
}
