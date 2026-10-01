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
      <body>{children}</body>
    </html>
  );
}
