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
      className="animate-fade-rise rounded-lg border border-rose-200 bg-rose-50/60 p-6 sm:p-7"
    >
      <div className="flex items-start gap-3.5">
        <span
          aria-hidden="true"
          className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-rose-300 bg-white text-sm font-bold text-rose-600"
        >
          !
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-serif text-lg font-semibold text-ink-900">{title}</h2>
          {detail ? (
            <p className="mt-1.5 break-words text-sm leading-relaxed text-ink-600">{detail}</p>
          ) : null}
          {hint ? <p className="mt-2 text-sm leading-relaxed text-ink-500">{hint}</p> : null}

          {error instanceof ApiError && error.status ? (
            <p className="tnum mt-2.5 text-2xs uppercase tracking-[0.1em] text-ink-400">
              HTTP {error.status}
            </p>
          ) : null}

          <div className="mt-5 flex flex-wrap gap-2.5">
            {retryable && onRetry ? (
              <button
                type="button"
                onClick={onRetry}
                className="rounded-md bg-ink-900 px-4 py-2 text-sm font-semibold text-paper-50 transition hover:bg-ink-700"
              >
                Try again
              </button>
            ) : null}
            <button
              type="button"
              onClick={onNewClaim}
              className="rounded-md border border-paper-300 bg-white px-4 py-2 text-sm font-medium text-ink-700 transition hover:border-ink-400"
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
        title: 'Investigation cancelled',
        detail: null,
        hint: 'You stopped waiting for the result. The backend may still be running the investigation.',
        retryable: true,
      };
    }
    if (error.status === null) {
      return {
        title: 'Cannot reach the backend',
        detail: error.message,
        hint: 'Confirm the API is running and that NEXT_PUBLIC_API_URL points at it.',
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
    if (error.status >= 500) {
      return {
        title: 'The investigation failed',
        detail: error.message,
        hint: 'The backend ran the pipeline and could not complete it. Retrying will start a fresh run.',
        retryable: true,
      };
    }
    return { title: 'Request failed', detail: error.message, hint: null, retryable: true };
  }

  if (error instanceof Error) {
    return { title: 'Something went wrong', detail: error.message, hint: null, retryable: true };
  }

  return {
    title: 'Something went wrong',
    detail: 'An unexpected error occurred.',
    hint: null,
    retryable: true,
  };
}
