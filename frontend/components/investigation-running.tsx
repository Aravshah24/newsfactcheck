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
  onCancelInvestigation,
  claimId,
}: {
  claim: string;
  elapsedSeconds: number;
  onCancel: () => void;
  onCancelInvestigation?: () => Promise<void>;
  claimId?: number;
}) {
  const [cancelling, setCancelling] = useState(false);

  const handleCancelInvestigation = async () => {
    if (!claimId || !onCancelInvestigation) return;
    setCancelling(true);
    try {
      await onCancelInvestigation();
    } finally {
      setCancelling(false);
    }
  };

  return (
    <div className="animate-fade-rise rounded-lg border border-[#D1D5DB] bg-[#F9FAFB]/92 backdrop-blur-md p-6 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="label-micro">Investigation in progress</p>
          <p className="mt-2 font-serif text-lg leading-relaxed text-[#111827]">{claim}</p>
        </div>
        <div className="text-right">
          <p className="tnum text-2xl font-semibold text-[#111827]" aria-live="off">
            {formatElapsed(elapsedSeconds)}
          </p>
          <p className="text-2xs uppercase tracking-[0.14em] text-[#6B7280]">elapsed</p>
        </div>
      </div>

      <div className="mt-6 h-1 w-full overflow-hidden rounded-full bg-[#E5E7EB]" role="presentation">
        <div className="h-full w-1/3 animate-sweep rounded-full bg-[#1F2937]" />
      </div>

      <p className="mt-4 text-sm leading-relaxed text-[#4B5563]">
        The backend runs each investigation synchronously and returns only when the report is complete.
        This typically takes one to two minutes.
      </p>

      <ul className="mt-5 space-y-2.5">
        {STAGES.map((stage) => (
          <li key={stage} className="flex gap-3 text-sm text-[#4B5563]">
            <span aria-hidden="true" className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-[#9CA3AF]" />
            <span>{stage}</span>
          </li>
        ))}
      </ul>

      <div className="mt-6 border-t border-[#D1D5DB] pt-4">
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="text-sm font-medium text-[#4B5563] underline decoration-[#D1D5DB] underline-offset-4 transition hover:text-[#111827] hover:decoration-[#4B5563]"
          >
            Stop waiting
          </button>
          {claimId && onCancelInvestigation && (
            <button
              type="button"
              onClick={handleCancelInvestigation}
              disabled={cancelling}
              className="text-sm font-medium text-rose-600 underline decoration-rose-300 underline-offset-4 transition hover:text-rose-900 hover:decoration-rose-400 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {cancelling ? 'Cancelling…' : 'Cancel investigation'}
            </button>
          )}
        </div>
        <p className="mt-1.5 text-xs leading-relaxed text-[#6B7280]">
          <strong className="text-[#111827]">Stop waiting:</strong> Backend keeps working; you can reopen the investigation from the list below.
        </p>
      </div>
    </div>
  );
}

export function useElapsed(running: boolean): number {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!running) {
      setSeconds(0);
      return;
    }
    const started = Date.now();
    const interval = setInterval(() => {
      setSeconds(Math.floor((Date.now() - started) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [running]);

  return seconds;
}

function formatElapsed(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}
