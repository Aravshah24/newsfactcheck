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
      <header className="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5">
        <h2 className="inline-flex items-center rounded-md border border-[#D1D5DB] bg-[#F3F4F6]/95 px-2.5 py-1 text-xs font-bold uppercase tracking-[0.14em] text-[#1F2937] shadow-sm backdrop-blur-md">
          {title}
        </h2>
        {aside ? (
          <div className="rounded-md border border-[#D1D5DB] bg-[#F3F4F6]/95 px-2.5 py-1 text-xs font-medium text-[#4B5563] shadow-sm backdrop-blur-md">
            {aside}
          </div>
        ) : null}
      </header>
      {hint ? (
        <p className="mb-4 max-w-2xl rounded-lg border border-[#D1D5DB] bg-[#F3F4F6]/95 px-3.5 py-2 text-xs leading-relaxed text-[#4B5563] shadow-sm backdrop-blur-md">
          {hint}
        </p>
      ) : null}
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
      className={`inline-flex shrink-0 items-center rounded-full border font-semibold ${descriptor.chip} ${sizing} shadow-sm`}
    >
      <span aria-hidden="true" className="leading-none">
        {descriptor.glyph}
      </span>
      <span>{descriptor.label}</span>
    </span>
  );
}

/** Bordered content panel. High-opacity frosted surface so content is completely legible. */
export function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-[#D1D5DB] bg-[#F9FAFB]/95 shadow-md backdrop-blur-md ${className}`}>
      {children}
    </div>
  );
}

export function Stat({ label, value, note }: { label: string; value: ReactNode; note?: ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="label-micro">{label}</p>
      <p className="mt-1 truncate text-lg font-semibold tnum text-[#111827]">{value}</p>
      {note ? <p className="mt-0.5 text-xs leading-snug text-[#6B7280]">{note}</p> : null}
    </div>
  );
}

export function EmptyNote({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-[#D1D5DB] bg-[#F9FAFB]/95 px-4 py-3 text-sm text-[#4B5563] shadow-sm backdrop-blur-md">
      {children}
    </p>
  );
}

/** An F beside a short connected trail of nodes: the evidence path. */
export function LogoMark() {
  return (
    <svg viewBox="0 0 36 36" aria-hidden="true" className="h-9 w-9 shrink-0">
      <rect width="36" height="36" rx="7" className="fill-[#1F2937]" />
      <text
        x="12.5"
        y="25"
        className="fill-[#F9FAFB]"
        fontFamily="Georgia, 'Times New Roman', serif"
        fontSize="20"
        fontWeight="700"
        textAnchor="middle"
      >
        F
      </text>
      <path
        d="M23 11.5 L29 16 L23 20.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="text-[#F9FAFB] opacity-50"
      />
      <circle cx="23" cy="11.5" r="1.9" className="fill-[#F9FAFB]" />
      <circle cx="29" cy="16" r="1.9" className="fill-[#F9FAFB] opacity-70" />
      <circle cx="23" cy="20.5" r="1.9" className="fill-[#F9FAFB] opacity-40" />
    </svg>
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
        <li key={`${index}-${item}`} className="flex gap-2.5 text-sm leading-relaxed text-[#4B5563]">
          <span aria-hidden="true" className="mt-0.5 shrink-0 text-[#9CA3AF]">
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
      className={`inline max-w-full break-words text-[#4B5563] underline decoration-[#D1D5DB] underline-offset-4 transition hover:text-[#111827] hover:decoration-[#4B5563] [overflow-wrap:anywhere] ${className}`}
    >
      {children}
      <svg
        aria-hidden="true"
        viewBox="0 0 12 12"
        className="ml-1 inline-block h-3 w-3 shrink-0 align-[-1px]"
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
