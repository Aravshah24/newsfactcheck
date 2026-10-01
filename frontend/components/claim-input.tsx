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
      <label htmlFor={fieldId} className="label-micro block">
        Claim to investigate
      </label>

      <div
        className={`mt-2 rounded-lg border bg-white transition focus-within:ring-2 focus-within:ring-ink-800 focus-within:ring-offset-2 focus-within:ring-offset-paper-50 ${
          touched && invalid ? 'border-rose-400' : 'border-paper-300'
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
          className="w-full resize-y rounded-lg bg-transparent px-4 py-3.5 font-serif text-lg leading-relaxed text-ink-900 outline-none placeholder:font-sans placeholder:text-base placeholder:text-ink-300 disabled:opacity-60"
        />

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-paper-200 px-4 py-2.5">
          <p className={`tnum text-2xs ${tooLong ? 'font-semibold text-rose-600' : 'text-ink-400'}`}>
            {tooLong ? `${claim.length - MAX_CLAIM_LENGTH} over the limit` : `${remaining} characters left`}
          </p>
          <button
            type="submit"
            disabled={busy || disabled || invalid}
            className="inline-flex items-center gap-2 rounded-md bg-ink-900 px-4 py-2 text-sm font-semibold text-paper-50 transition hover:bg-ink-700 disabled:cursor-not-allowed disabled:opacity-40"
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
        <p id={errorId} role="alert" className="mt-2 text-sm font-medium text-rose-600">
          {tooLong ? 'This claim is too long to investigate.' : 'Enter a claim to investigate.'}
        </p>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-2xs uppercase tracking-[0.14em] text-ink-400">Try</span>
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            disabled={busy || disabled}
            onClick={() => {
              setClaim(example);
              setTouched(false);
            }}
            className="max-w-full truncate rounded-full border border-paper-300 bg-white px-3 py-1 text-left text-xs text-ink-600 transition hover:border-ink-400 hover:text-ink-900 disabled:opacity-50"
          >
            {example}
          </button>
        ))}
      </div>
    </form>
  );
}
