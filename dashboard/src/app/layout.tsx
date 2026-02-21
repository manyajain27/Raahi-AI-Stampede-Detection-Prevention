import type { Metadata } from 'next';
import './globals.css';
import Sidebar from '@/components/Sidebar';

export const metadata: Metadata = {
  title: 'Raahi — Crowd Intelligence Platform',
  description: 'AI-powered crowd management and event safety platform',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="h-screen overflow-hidden">
        <div className="flex h-full">
          <Sidebar />
          <main className="flex-1 ml-[260px] h-full overflow-hidden">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
