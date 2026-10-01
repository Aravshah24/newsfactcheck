import type { ReactNode } from 'react';

import type { Descriptor } from '@/lib/format';

export function Section({
  id,
  title,
  hint,
  aside,
  children,
}: {
  id?: string;
  title: string;
  hint?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-24">
      <header className="mb-4 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="text-sm font-semibold uppercase tracking-[0.12em] text-ink-500">{title}</h2>
        {aside ? <div className="text-xs text-ink-400">{aside}</div> : null}
      </header>
      {hint ? <p className="mb-4 max-w-2xl text-sm leading-relaxed text-ink-500">{hint}</p> : null}
      {children}
    </section>
  );
}

/**
 * Verdict and stance badge. The glyph and the written label both carry the
 * meaning, so the badge stays readable without colour perception.
 */
export function VerdictChip({ descriptor, size = 'md' }: { descriptor: Descriptor; size?: 'sm' | 'md' | 'lg' }) {
  const sizing =
    size === 'lg'
      ? 'gap-2.5 px-3.5 py-1.5 text-sm'
      : size === 'sm'
        ? 'gap-1.5 px-2 py-0.5 text-2xs'
        : 'gap-2 px-2.5 py-1 text-xs';

  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full border font-semibold ${descriptor.chip} ${sizing}`}
    >
      <span aria-hidden="true" className="leading-none">
        {descriptor.glyph}
      </span>
      <span>{descriptor.label}</span>
    </span>
  );
}

/** Bordered content panel. Hairline edge, no shadow, so sections read as one sheet. */
export function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-paper-200 bg-white ${className}`}>{children}</div>
  );
}

export function Stat({ label, value, note }: { label: string; value: ReactNode; note?: ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="label-micro">{label}</p>
      <p className="mt-1 truncate text-lg font-semibold tnum text-ink-800">{value}</p>
      {note ? <p className="mt-0.5 text-xs leading-snug text-ink-400">{note}</p> : null}
    </div>
  );
}

export function EmptyNote({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-md border border-dashed border-paper-300 bg-paper-100 px-4 py-3 text-sm text-ink-500">
      {children}
    </p>
  );
}

/** Renders a plain list of strings, tolerating null and empty input. */
export function BulletList({ items, glyph = '—' }: { items: readonly string[] | null | undefined; glyph?: string }) {
  if (!items || items.length === 0) {
    return null;
  }
  return (
    <ul className="space-y-2">
      {items.map((item, index) => (
        <li key={`${index}-${item}`} className="flex gap-2.5 text-sm leading-relaxed text-ink-700">
          <span aria-hidden="true" className="mt-0.5 shrink-0 text-ink-300">
            {glyph}
          </span>
          <span className="min-w-0">{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function ExternalLink({
  href,
  children,
  className = '',
}: {
  href: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center gap-1.5 text-ink-600 underline decoration-paper-300 underline-offset-4 transition hover:text-ink-900 hover:decoration-ink-400 ${className}`}
    >
      {children}
      <svg
        aria-hidden="true"
        viewBox="0 0 12 12"
        className="h-3 w-3 shrink-0"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M4.5 2.5h5v5" />
        <path d="M9.5 2.5 5 7" />
        <path d="M8 9.5v0a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1h0" />
      </svg>
    </a>
  );
}
