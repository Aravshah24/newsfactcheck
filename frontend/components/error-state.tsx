'use client';

import { ApiError } from '@/lib/api';

export function ErrorState({
  error,
  onRetry,
  onNewClaim,
}: {
  error: unknown;
  onRetry?: () => void;
  onNewClaim: () => void;
}) {
  const { title, detail, hint, retryable } = describe(error);

  return (
    <div
      role="alert"
      className="animate-fade-rise rounded-lg border border-rose-200 bg-rose-50/80 p-6 sm:p-7 backdrop-blur-md"
    >
      <div className="flex items-start gap-3.5">
        <span
          aria-hidden="true"
          className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-rose-300 bg-[#F9FAFB] text-sm font-bold text-rose-600"
        >
          !
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-serif text-lg font-semibold text-[#111827]">{title}</h2>
          {detail ? (
            <p className="mt-1.5 break-words text-sm leading-relaxed text-[#4B5563]">{detail}</p>
          ) : null}
          {hint ? <p className="mt-2 text-sm leading-relaxed text-[#4B5563]">{hint}</p> : null}

          {error instanceof ApiError && error.status ? (
            <p className="tnum mt-2.5 text-2xs uppercase tracking-[0.1em] text-[#6B7280]">
              HTTP {error.status}
            </p>
          ) : null}

          <div className="mt-5 flex flex-wrap gap-2.5">
            {retryable && onRetry ? (
              <button
                type="button"
                onClick={onRetry}
                className="rounded-md bg-[#1F2937] px-4 py-2 text-sm font-semibold text-[#F9FAFB] transition hover:bg-[#111827]"
              >
                Try again
              </button>
            ) : null}
            <button
              type="button"
              onClick={onNewClaim}
              className="rounded-md border border-[#D1D5DB] bg-[#F9FAFB]/92 backdrop-blur-md px-4 py-2 text-sm font-medium text-[#374151] transition hover:border-[#4B5563] hover:text-[#111827]"
            >
              Investigate another claim
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function describe(error: unknown): {
  title: string;
  detail: string | null;
  hint: string | null;
  retryable: boolean;
} {
  if (error instanceof ApiError) {
    if (error.detail === 'cancelled') {
      return {
        title: 'Rate limit reached',
        detail: error.message,
        hint: 'Too many investigations submitted recently. Wait a minute and try again.',
        retryable: true,
      };
    }
    if (error.status === null) {
      return {
        title: 'Backend error',
        detail: error.message,
        hint: 'The backend returned an unexpected response. Try again in a moment.',
        retryable: true,
      };
    }
    if (error.status === 422) {
      return {
        title: 'The claim was rejected',
        detail: error.message,
        hint: 'The backend validates the claim before starting a run.',
        retryable: false,
      };
    }
    if (error.status === 404) {
      return {
        title: 'Investigation not found',
        detail: error.message,
        hint: 'That id does not match a stored investigation.',
        retryable: false,
      };
    }
    if (error.status === 429) {
      return {
        title: 'Rate limit reached',
        detail: error.message,
        hint: 'Too many investigations submitted recently. Wait a minute and try again.',
        retryable: true,
      };
    }
    return { title: 'Backend error', detail: error.message, hint: null, retryable: true };
  }

  if (error instanceof Error) {
    if (error.name === 'AbortError') {
      return {
        title: 'Request was cancelled',
        detail: null,
        hint: null,
        retryable: true,
      };
    }
    return {
      title: 'Investigation failed',
      detail: error.message,
      hint: 'An unexpected error occurred in the browser.',
      retryable: true,
    };
  }

  return {
    title: 'Investigation failed',
    detail: 'An unknown error occurred.',
    hint: null,
    retryable: true,
  };
}
