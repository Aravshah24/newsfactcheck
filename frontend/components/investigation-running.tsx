'use client';

import { useEffect, useState } from 'react';

/**
 * The backend runs the pipeline synchronously and reports no intermediate
 * stage, so this shows honest elapsed time and a description of the work
 * rather than a fabricated progress percentage or a claim about which agent is
 * currently running.
 */
const STAGES = [
  'Decomposing the claim into atomic subclaims',
  'Retrieving sources and searching for opposing records',
  'Assessing each document against the complete claim',
  'Grouping sources by independence',
  'Checking completeness and verifying each subclaim',
  'Writing the research report',
];

export function InvestigationRunning({
  claim,
  elapsedSeconds,
  onCancel,
}: {
  claim: string;
  elapsedSeconds: number;
  onCancel: () => void;
}) {
  return (
    <div className="animate-fade-rise rounded-lg border border-paper-200 bg-white p-6 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="label-micro">Investigation in progress</p>
          <p className="mt-2 font-serif text-lg leading-relaxed text-ink-900">{claim}</p>
        </div>
        <div className="text-right">
          <p className="tnum text-2xl font-semibold text-ink-800" aria-live="off">
            {formatElapsed(elapsedSeconds)}
          </p>
          <p className="text-2xs uppercase tracking-[0.14em] text-ink-400">elapsed</p>
        </div>
      </div>

      <div className="mt-6 h-1 w-full overflow-hidden rounded-full bg-paper-200" role="presentation">
        <div className="h-full w-1/3 animate-sweep rounded-full bg-ink-400" />
      </div>

      <p className="mt-4 text-sm leading-relaxed text-ink-500">
        The backend runs each investigation synchronously and returns only when the report is complete.
        This typically takes one to two minutes.
      </p>

      <ul className="mt-5 space-y-2.5">
        {STAGES.map((stage) => (
          <li key={stage} className="flex gap-3 text-sm text-ink-500">
            <span aria-hidden="true" className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-ink-300" />
            <span>{stage}</span>
          </li>
        ))}
      </ul>

      <div className="mt-6 border-t border-paper-200 pt-4">
        <button
          type="button"
          onClick={onCancel}
          className="text-sm font-medium text-ink-600 underline decoration-paper-300 underline-offset-4 transition hover:text-ink-900 hover:decoration-ink-400"
        >
          Stop waiting
        </button>
        <p className="mt-1.5 text-xs leading-relaxed text-ink-400">
          This stops waiting for the response. The backend keeps working, and the finished investigation
          will be stored and can be reopened by its id.
        </p>
      </div>
    </div>
  );
}

/** Ticks once a second so elapsed time advances while the request is in flight. */
export function useElapsed(active: boolean): number {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!active) return;
    setSeconds(0);
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      setSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [active]);

  return seconds;
}

function formatElapsed(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}
