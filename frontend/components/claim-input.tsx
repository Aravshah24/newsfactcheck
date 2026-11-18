'use client';

import { FormEvent, useId, useState } from 'react';

import { MAX_CLAIM_LENGTH } from '@/lib/api';

const EXAMPLES = [
  "India's Chandrayaan-3 mission successfully landed on the Moon in 2023.",
  'The city reduced traffic by 20% after the new lane opened.',
  'Global temperatures rose by 1.5 degrees Celsius last year.',
];

export function ClaimInput({
  onSubmit,
  busy,
  disabled,
}: {
  onSubmit: (claim: string) => void;
  busy: boolean;
  disabled?: boolean;
}) {
  const [claim, setClaim] = useState('');
  const [touched, setTouched] = useState(false);
  const fieldId = useId();
  const errorId = useId();

  const trimmed = claim.trim();
  const tooLong = claim.length > MAX_CLAIM_LENGTH;
  const empty = trimmed.length === 0;
  const invalid = tooLong || empty;
  const remaining = MAX_CLAIM_LENGTH - claim.length;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setTouched(true);
    if (invalid || busy) return;
    onSubmit(trimmed);
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <label htmlFor={fieldId} className="block mb-2">
        <span className="inline-block rounded-md border border-[#D1D5DB] bg-[#F3F4F6]/95 px-2.5 py-1 text-2xs font-bold uppercase tracking-[0.14em] text-[#1F2937] shadow-sm backdrop-blur-md">
          Claim to investigate
        </span>
      </label>

      <div
        className={`rounded-2xl border bg-[#F9FAFB]/95 shadow-md backdrop-blur-md transition focus-within:ring-2 focus-within:ring-[#1F2937] focus-within:ring-offset-2 focus-within:ring-offset-[#F3F4F6] ${
          touched && invalid ? 'border-rose-400' : 'border-[#D1D5DB]'
        }`}
      >
        <textarea
          id={fieldId}
          value={claim}
          disabled={busy || disabled}
          onChange={(event) => setClaim(event.target.value)}
          onBlur={() => setTouched(true)}
          rows={3}
          spellCheck
          aria-invalid={touched && invalid}
          aria-describedby={touched && invalid ? errorId : undefined}
          placeholder="Paste a claim exactly as it was published."
          className="w-full resize-y rounded-t-2xl bg-transparent px-4 py-3.5 font-serif text-lg leading-relaxed text-[#111827] outline-none placeholder:font-sans placeholder:text-base placeholder:text-[#6B7280] disabled:opacity-60"
        />

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[#D1D5DB] bg-[#E5E7EB]/90 rounded-b-2xl px-4 py-2.5">
          <p className={`tnum text-2xs ${tooLong ? 'font-semibold text-rose-600' : 'text-[#6B7280]'}`}>
            {tooLong ? `${claim.length - MAX_CLAIM_LENGTH} over the limit` : `${remaining} characters left`}
          </p>
          <button
            type="submit"
            disabled={busy || disabled || invalid}
            className="inline-flex items-center gap-2 rounded-md bg-[#1F2937] px-4 py-2 text-sm font-semibold text-[#F9FAFB] shadow-sm transition hover:bg-[#111827] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? 'Investigating…' : 'Investigate'}
            <svg
              aria-hidden="true"
              viewBox="0 0 16 16"
              className="h-3.5 w-3.5"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M3 8h10" />
              <path d="M9 4l4 4-4 4" />
            </svg>
          </button>
        </div>
      </div>

      {touched && invalid ? (
        <p id={errorId} role="alert" className="mt-2 inline-block rounded-md border border-rose-200 bg-rose-50/95 px-3 py-1 text-sm font-medium text-rose-600 shadow-sm">
          {tooLong ? 'This claim is too long to investigate.' : 'Enter a claim to investigate.'}
        </p>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-[#D1D5DB] bg-[#F3F4F6]/95 px-4 py-2.5 shadow-sm backdrop-blur-md">
        <span className="text-2xs font-bold uppercase tracking-[0.14em] text-[#6B7280]">Try</span>
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            disabled={busy || disabled}
            onClick={() => {
              setClaim(example);
              setTouched(false);
            }}
            className="max-w-full truncate rounded-full border border-[#D1D5DB] bg-[#F9FAFB] px-3 py-1 text-left text-xs font-medium text-[#4B5563] shadow-sm transition hover:border-[#1F2937] hover:text-[#111827] disabled:opacity-50"
          >
            {example}
          </button>
        ))}
      </div>
    </form>
  );
}
