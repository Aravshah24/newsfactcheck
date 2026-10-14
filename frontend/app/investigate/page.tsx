'use client';

import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';

import {
  Completeness,
  MediaCoveragePanel,
  SourceIndependence,
} from '@/components/analysis-panels';
import { ClaimInput } from '@/components/claim-input';
import { ErrorState } from '@/components/error-state';
import { EvidenceList } from '@/components/evidence-list';
import { InvestigationRunning, useElapsed } from '@/components/investigation-running';
import { EmptyNote, LogoMark, Section, Stat } from '@/components/primitives';
import { ResearchReport } from '@/components/research-report';
import { VerdictSummary, VerificationList } from '@/components/verdict-summary';
import { API_BASE_URL, cancelInvestigation, createInvestigation, deleteInvestigation, getHealth, getInvestigation, listInvestigations } from '@/lib/api';
import { formatConfidence, formatDate, overallVerdictDescriptor } from '@/lib/format';
import type { InvestigationListItem, InvestigationStateResponse, LlmStatus, ServiceHealth } from '@/lib/types';

type Phase = 'idle' | 'running' | 'done' | 'error';

export default function Home() {
  const [phase, setPhase] = useState<Phase>('idle');
  const [result, setResult] = useState<InvestigationStateResponse | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [activeClaim, setActiveClaim] = useState('');
  // Holds how the current attempt should be repeated, so a failure can offer a
  // real retry whether it came from submitting a claim or from opening an id.
  const [retry, setRetry] = useState<(() => void) | null>(null);
  const [health, setHealth] = useState<ServiceHealth | null>(null);
  const [healthError, setHealthError] = useState(false);
  const [recent, setRecent] = useState<InvestigationListItem[]>([]);
  const [recentTotal, setRecentTotal] = useState(0);
  const [recentLoading, setRecentLoading] = useState(false);
  const [recentError, setRecentError] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const elapsed = useElapsed(phase === 'running');

  const loadRecent = useCallback(() => {
    setRecentLoading(true);
    setRecentError(false);
    listInvestigations()
      .then((data) => {
        setRecent(data.items);
        setRecentTotal(data.total);
      })
      .catch(() => setRecentError(true))
      .finally(() => setRecentLoading(false));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;

    // Poll rather than probe once: the backend may still be starting or briefly
    // restarting, so a single early failure must not pin the indicator to
    // "unreachable" for the rest of the session.
    const check = async () => {
      try {
        const status = await getHealth(controller.signal);
        setHealth(status);
        setHealthError(false);
      } catch {
        if (!controller.signal.aborted) {
          setHealthError(true);
        }
      } finally {
        if (!controller.signal.aborted) {
          timer = setTimeout(check, 15000);
        }
      }
    };

    void check();
    return () => {
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    loadRecent();
  }, [loadRecent]);

  // Investigations are persisted, so a result can be reopened or shared by id.
  const deepLinkHandled = useRef(false);
  useEffect(() => {
    if (deepLinkHandled.current) return;
    deepLinkHandled.current = true;
    const requested = new URLSearchParams(window.location.search).get('claim');
    if (requested && /^\d+$/.test(requested)) {
      void runOpen(Number(requested));
    }
    // Intentionally runs once on mount only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = useCallback(async (claim: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setPhase('running');
    setError(null);
    setResult(null);
    setActiveClaim(claim);
    setRetry(() => () => void run(claim));

    try {
      // The backend runs the pipeline synchronously, so this resolves only when
      // the investigation is finished and persisted.
      const created = await createInvestigation(claim, controller.signal);
      const detail = await getInvestigation(created.claim_id, controller.signal);
      setResult(detail);
      setPhase('done');
      setAddressBar(created.claim_id);
      loadRecent();
    } catch (caught) {
      setError(caught);
      setPhase('error');
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
    }
  }, [loadRecent]);

  function handleSubmit(claim: string) {
    void run(claim);
  }

  async function handleDelete(claimId: number) {
    try {
      await deleteInvestigation(claimId);
      setRecent((previous) => previous.filter((item) => item.claim_id !== claimId));
      setRecentTotal((total) => Math.max(0, total - 1));
    } catch {
      // A failed delete should not leave the list silently stale.
      loadRecent();
    }
  }

  function handleOpenById(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const value = String(form.get('claimId') ?? '').trim();
    if (!/^\d+$/.test(value)) return;
    void runOpen(Number(value));
  }

  async function runOpen(claimId: number) {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setPhase('running');
    setError(null);
    setResult(null);
    setActiveClaim(`Investigation #${claimId}`);
    setRetry(() => () => void runOpen(claimId));

    try {
      const detail = await getInvestigation(claimId, controller.signal);
      setResult(detail);
      setPhase('done');
      setAddressBar(claimId);
    } catch (caught) {
      setError(caught);
      setPhase('error');
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
    }
  }

  function reset() {
    abortRef.current?.abort();
    setPhase('idle');
    setResult(null);
    setError(null);
    setActiveClaim('');
    setRetry(null);
    setAddressBar(null);
    loadRecent();
  }

  return (
    <div className="min-h-screen">
      <SiteHeader health={health} healthError={healthError} />

      <main className="mx-auto w-full max-w-[86rem] px-5 pb-24 pt-10 sm:px-8 sm:pt-14">
        {phase !== 'done' || !result ? (
          <section className={phase === 'running' ? 'mx-auto max-w-3xl' : 'mx-auto max-w-3xl'}>
            <Intro phase={phase} />
            <div className="mt-8">
              <ClaimInput onSubmit={handleSubmit} busy={phase === 'running'} />
            </div>

            {phase === 'running' ? (
              <div className="mt-6">
                <InvestigationRunning
                  claim={activeClaim}
                  elapsedSeconds={elapsed}
                  onCancel={() => abortRef.current?.abort()}
                  onCancelInvestigation={async () => {
                    const controller = new AbortController();
                    try {
                      await cancelInvestigation(result?.claim_id || 0, controller.signal);
                    } catch {
                      // Ignore errors; the backend will handle cancellation
                    }
                  }}
                  claimId={result?.claim_id}
                />
              </div>
            ) : null}

            {phase === 'error' ? (
              <div className="mt-6">
                <ErrorState
                  error={error}
                  onRetry={retry ?? undefined}
                  onNewClaim={reset}
                />
              </div>
            ) : null}

            {phase === 'idle' ? (
              <div className="mt-10">
                <RecentInvestigations
                  items={recent}
                  total={recentTotal}
                  loading={recentLoading}
                  error={recentError}
                  onOpen={(claimId) => void runOpen(claimId)}
                  onDelete={(claimId) => void handleDelete(claimId)}
                  onRefresh={loadRecent}
                  onSubmitId={handleOpenById}
                />
              </div>
            ) : null}
          </section>
        ) : null}

        {phase === 'done' && result ? (
          <ResultsView
            result={result}
            onReset={reset}
            onRerun={(claim) => void run(claim)}
          />
        ) : null}
      </main>

      <footer className="border-t border-paper-200 px-5 py-8 sm:px-8">
        <div className="mx-auto flex max-w-[86rem] flex-wrap items-center justify-between gap-3 text-2xs text-ink-400">
          <p>
            Verdicts are research aids, not calibrated truth. Confidence is capped by independent
            source groups, not by how many articles were retrieved.
          </p>
          <p className="tnum">API · {API_BASE_URL}</p>
        </div>
      </footer>
    </div>
  );
}

function SiteHeader({ health, healthError }: { health: ServiceHealth | null; healthError: boolean }) {
  return (
    <header className="border-b border-paper-200 bg-paper-100/60">
      <div className="mx-auto flex max-w-[86rem] flex-wrap items-center justify-between gap-4 px-5 py-4 sm:px-8">
        <Link href="/" className="flex items-center gap-3" aria-label="FactTrace home">
          <LogoMark />
          <div>
            <p className="font-serif text-base font-semibold leading-none tracking-tight text-ink-900">
              FactTrace
            </p>
            <p className="mt-1 text-2xs uppercase tracking-[0.14em] text-ink-400">
              Evidence-backed claim investigation
            </p>
          </div>
        </Link>

        <ServiceIndicator health={health} healthError={healthError} />
      </div>
    </header>
  );
}



function ServiceIndicator({ health, healthError }: { health: ServiceHealth | null; healthError: boolean }) {
  if (healthError) {
    return <StatusPill tone="negative" glyph="✕" label="API unreachable" />;
  }
  if (!health) {
    return <StatusPill tone="neutral" glyph="·" label="Checking API…" />;
  }

  const llm: LlmStatus = health.llm;
  if (!llm.available) {
    return (
      <StatusPill
        tone="caution"
        glyph="!"
        label="API up · no live reasoning"
        title={llm.remediation ?? llm.error ?? 'The backend has no usable LLM provider configured.'}
      />
    );
  }
  return <StatusPill tone="positive" glyph="✓" label={`API up · ${llm.model ?? 'model ready'}`} />;
}

function StatusPill({
  tone,
  glyph,
  label,
  title,
}: {
  tone: 'positive' | 'negative' | 'caution' | 'neutral';
  glyph: string;
  label: string;
  title?: string;
}) {
  const tones = {
    positive: 'border-emerald-300 bg-emerald-50 text-emerald-800',
    negative: 'border-rose-300 bg-rose-50 text-rose-800',
    caution: 'border-amber-300 bg-amber-50 text-amber-800',
    neutral: 'border-paper-300 bg-white text-ink-500',
  } as const;

  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-2xs font-medium ${tones[tone]}`}
    >
      <span aria-hidden="true">{glyph}</span>
      <span className="max-w-[16rem] truncate">{label}</span>
    </span>
  );
}

function Intro({ phase }: { phase: Phase }) {
  if (phase === 'running') return null;
  return (
    <div>
      <p className="label-micro">Investigate a claim</p>
      <h1 className="mt-3 max-w-2xl font-serif text-3xl font-semibold leading-[1.15] tracking-tight text-ink-900 sm:text-[2.5rem]">
        Trace the evidence.
        <br />
        See what the sources actually support.
      </h1>
    </div>
  );
}

function OpenExisting({ onSubmit }: { onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  return (
    <form onSubmit={onSubmit} className="flex flex-wrap items-center gap-3">
      <label htmlFor="claimId" className="text-xs text-ink-400">
        Reopen by id
      </label>
      <input
        id="claimId"
        name="claimId"
        type="number"
        min={1}
        inputMode="numeric"
        placeholder="60"
        className="tnum w-24 rounded-md border border-paper-300 bg-white px-2.5 py-1.5 text-sm text-ink-800 outline-none focus-visible:ring-2 focus-visible:ring-ink-800"
      />
      <button
        type="submit"
        className="rounded-md border border-paper-300 bg-white px-3 py-1.5 text-sm font-medium text-ink-700 transition hover:border-ink-400"
      >
        Open
      </button>
    </form>
  );
}

function RecentInvestigations({
  items,
  total,
  loading,
  error,
  onOpen,
  onDelete,
  onRefresh,
  onSubmitId,
}: {
  items: InvestigationListItem[];
  total: number;
  loading: boolean;
  error: boolean;
  onOpen: (claimId: number) => void;
  onDelete: (claimId: number) => void;
  onRefresh: () => void;
  onSubmitId: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <div className="space-y-4 border-t border-paper-200 pt-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="label-micro">Stored investigations</p>
          <p className="mt-1 text-xs text-ink-400">
            {total > 0 ? `${total} saved. Reopen or remove a previous run.` : 'Reopen a previous run.'}
          </p>
        </div>
        <OpenExisting onSubmit={onSubmitId} />
      </div>

      {loading && items.length === 0 ? (
        <p className="text-xs text-ink-400">Loading stored investigations…</p>
      ) : error ? (
        <button
          type="button"
          onClick={onRefresh}
          className="text-xs font-medium text-ink-600 underline underline-offset-2"
        >
          Could not load stored investigations. Retry.
        </button>
      ) : items.length === 0 ? (
        <p className="text-xs text-ink-400">No stored investigations yet.</p>
      ) : (
        <ul className="divide-y divide-paper-200 overflow-hidden rounded-lg border border-paper-200 bg-white">
          {items.map((item) => {
            const descriptor = overallVerdictDescriptor(item.overall_verdict);
            return (
              <li key={item.claim_id} className="flex items-center gap-3 px-4 py-3">
                <button
                  type="button"
                  onClick={() => onOpen(item.claim_id)}
                  className="min-w-0 flex-1 text-left"
                >
                  <span className="block truncate text-sm text-ink-800">{item.claim_text}</span>
                  <span className="tnum mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-2xs uppercase tracking-[0.12em] text-ink-400">
                    <span>#{item.claim_id}</span>
                    <span className={`rounded-full border px-1.5 py-0.5 normal-case tracking-normal ${descriptor.chip}`}>
                      {descriptor.label}
                    </span>
                    {item.overall_confidence != null ? (
                      <span>{formatConfidence(item.overall_confidence)}</span>
                    ) : null}
                    <span>{item.evidence_count} evidence</span>
                    {item.created_at ? <span>{formatDate(item.created_at)}</span> : null}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(item.claim_id)}
                  className="shrink-0 rounded-md border border-paper-300 bg-white px-2.5 py-1 text-xs font-medium text-ink-500 transition hover:border-rose-300 hover:text-rose-700"
                >
                  Delete
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function ResultsView({
  result,
  onReset,
  onRerun,
}: {
  result: InvestigationStateResponse;
  onReset: () => void;
  onRerun: (claim: string) => void;
}) {
  const stats = result.retrieval_stats;
  const independence = result.source_independence;

  return (
    <div className="animate-fade-rise space-y-14">
      <section>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <p className="label-micro">Claim under investigation</p>
            <h1 className="mt-2.5 max-w-3xl font-serif text-2xl font-semibold leading-snug tracking-tight text-ink-900 sm:text-[1.75rem]">
              {result.claim_text}
            </h1>
            <p className="tnum mt-3 text-2xs uppercase tracking-[0.12em] text-ink-400">
              Investigation #{result.claim_id}
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            <button
              type="button"
              onClick={() => onRerun(result.claim_text)}
              className="rounded-md border border-paper-300 bg-white px-3 py-1.5 text-sm font-medium text-ink-700 transition hover:border-ink-400"
            >
              Re-run
            </button>
            <button
              type="button"
              onClick={onReset}
              className="rounded-md bg-ink-900 px-3 py-1.5 text-sm font-semibold text-paper-50 transition hover:bg-ink-700"
            >
              New claim
            </button>
          </div>
        </div>

        <div className="mt-7">
          <VerdictSummary result={result} />
        </div>
      </section>

      <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_20rem] lg:gap-10 xl:gap-14">
        <div className="min-w-0 space-y-12">
          <Section
            id="verification"
            title="Subclaim verification"
            hint="Each part of the claim is checked on its own. A conclusion is stored separately from the evidence it rests on."
          >
            <VerificationList result={result} />
          </Section>

          <Section
            id="evidence"
            title="Evidence"
            aside={`${result.evidence.length} assessed ${result.evidence.length === 1 ? 'document' : 'documents'}`}
            hint="Every document below was compared with the complete subclaim, not just its topic. Context and neutral documents cannot raise confidence."
          >
            <EvidenceList
              evidence={result.evidence}
              subclaims={result.subclaims}
              independence={independence}
            />
          </Section>

          <Section
            id="report"
            title="Research report"
            hint="The conclusion, with the constraint that produced it made explicit."
          >
            <ResearchReport report={result.report} evidence={result.evidence} />
          </Section>
        </div>

        <aside className="min-w-0 space-y-10">
          <Section id="independence" title="Source independence">
            <SourceIndependence data={independence} />
          </Section>

          <Section id="completeness" title="Completeness">
            <Completeness data={result.completeness} />
          </Section>

          <Section id="media" title="Media coverage">
            <MediaCoveragePanel data={result.media_coverage} />
          </Section>

          <Section id="run-details" title="Run details">
            <div className="rounded-lg border border-paper-200 bg-white p-4">
              <dl className="space-y-3">
                {stats ? (
                  <>
                    <Row label="Searches run">
                      <Stat label="" value={stats.search_runs} />
                    </Row>
                    <Row label="Documents (raw / unique)">
                      <Stat label="" value={`${stats.raw_documents} / ${stats.unique_documents}`} />
                    </Row>
                  </>
                ) : null}
                <Row label="Documents found">
                  <Stat label="" value={independence?.documents_found ?? result.evidence.length} />
                </Row>
                <Row label="Live reasoning">
                  <Stat
                    label=""
                    value={result.llm_available ? 'Available' : 'Unavailable'}
                    note={result.llm_status?.model ?? undefined}
                  />
                </Row>
              </dl>

              {!result.llm_available ? (
                <div className="mt-4 border-t border-paper-200 pt-3.5">
                  <p className="text-xs leading-relaxed text-ink-500">
                    Without live reasoning the system cannot compare propositions, so it records
                    documents as non-probative rather than guessing.
                  </p>
                  {result.llm_status?.remediation ? (
                    <p className="mt-1.5 text-2xs leading-relaxed text-ink-400">
                      {result.llm_status.remediation}
                    </p>
                  ) : null}
                </div>
              ) : null}

              {result.errors.length > 0 ? (
                <div className="mt-4 border-t border-paper-200 pt-3.5">
                  <p className="label-micro mb-1.5">Errors during run</p>
                  <ul className="space-y-1">
                    {result.errors.slice(0, 5).map((item, index) => (
                      <li key={index} className="break-words text-2xs text-ink-500">
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          </Section>

          {result.evidence.length === 0 ? (
            <EmptyNote>
              No evidence was recorded for this claim, so the sections above describe what the system
              looked for rather than what it found.
            </EmptyNote>
          ) : null}
        </aside>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-xs text-ink-500">{label}</dt>
      <dd className="shrink-0 text-sm font-semibold text-ink-800">{children}</dd>
    </div>
  );
}

/** Keeps a finished investigation addressable and shareable. */
function setAddressBar(claimId: number | null) {
  if (typeof window === 'undefined') return;
  const url = new URL(window.location.href);
  if (claimId === null) {
    url.searchParams.delete('claim');
  } else {
    url.searchParams.set('claim', String(claimId));
  }
  window.history.replaceState(null, '', url.toString());
}
