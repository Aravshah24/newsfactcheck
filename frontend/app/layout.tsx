import type { Metadata } from 'next';

import './globals.css';

export const metadata: Metadata = {
  title: 'FactTrace — Evidence-backed claim investigation',
  description:
    'Investigate a news claim by decomposing it, retrieving sources, comparing evidence dimension by dimension, and weighing conclusions by source independence.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#F3F4F6] text-[#111827] antialiased">
        <div
          aria-hidden="true"
          className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
        >
          <div
            className="absolute inset-0 bg-cover bg-center grayscale opacity-[0.38] blur-none scale-105"
            style={{ backgroundImage: "url('/newspaper.jpg')" }}
          />
          <div className="absolute inset-0 bg-[#F3F4F6]/30" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(243,244,246,0.55)_0%,transparent_80%)]" />
        </div>
        {children}
      </body>
    </html>
  );
}
