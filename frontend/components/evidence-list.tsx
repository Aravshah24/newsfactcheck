'use client';

import { useMemo, useState } from 'react';

import {
  assessmentStatusLabel,
  categoryLabel,
  formatConfidence,
  isProbative,
  pluralise,
  publisherDomain,
  stanceDescriptor,
  titleCase,
} from '@/lib/format';
import type { EvidenceItem, SourceIndependence, Subclaim } from '@/lib/types';
import { EmptyNote, ExternalLink, VerdictChip } from './primitives';

type Filter = 'all' | 'probative' | 'supports' | 'contradicts';

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'probative', label: 'Probative' },
  { key: 'supports', label: 'Supports' },
  { key: 'contradicts', label: 'Contradicts' },
];

/**
 * Evidence is the centre of the product, so each item shows what it is, where
 * it came from, which subclaim it was compared against, and how that comparison
 * was decided. Retrieved documents that turned out to be probative are visibly
 * distinguished from those that did not.
 */
export function EvidenceList({
  evidence,
  subclaims,
  independence,
}: {
  evidence: EvidenceItem[];
  subclaims: Subclaim[];
  independence: SourceIndependence | null;
}) {
  const [filter, setFilter] = useState<Filter>('all');
  const [subclaimId, setSubclaimId] = useState<number | 'all'>('all');

  const groups = independence?.group_for_evidence ?? null;

  const counts = useMemo(
    () => ({
      all: evidence.length,
      probative: evidence.filter((item) => isProbative(item.stance)).length,
      supports: evidence.filter((item) => item.stance === 'supports').length,
      contradicts: evidence.filter((item) => item.stance === 'contradicts').length,
    }),
    [evidence],
  );

  const visible = useMemo(() => {
    return evidence
      .filter((item) => {
        if (subclaimId !== 'all' && item.subclaim_id !== subclaimId) return false;
        if (filter === 'all') return true;
        if (filter === 'probative') return isProbative(item.stance);
        return item.stance === filter;
      })
      .slice()
      .sort((a, b) => {
        // Probative first, then higher confidence, then stable by id.
        const rank = (item: EvidenceItem) => (isProbative(item.stance) ? 0 : 1);
        const byRank = rank(a) - rank(b);
        if (byRank !== 0) return byRank;
        const byConfidence = (b.confidence ?? 0) - (a.confidence ?? 0);
        if (byConfidence !== 0) return byConfidence;
        return (a.id ?? 0) - (b.id ?? 0);
      });
  }, [evidence, filter, subclaimId]);

  if (evidence.length === 0) {
    return (
      <EmptyNote>
        No evidence was recorded. This claim may be too recent, too local, or outside what the
        configured retrieval channels can reach. It is not evidence that the claim is true.
      </EmptyNote>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div
          className="flex flex-wrap items-center gap-1 rounded-md border border-paper-300 bg-white p-1"
          role="group"
          aria-label="Filter evidence by stance"
        >
          {FILTERS.map((option) => {
            const active = filter === option.key;
            return (
              <button
                key={option.key}
                type="button"
                onClick={() => setFilter(option.key)}
                aria-pressed={active}
                className={`rounded px-2.5 py-1 text-xs font-medium transition ${
                  active ? 'bg-ink-900 text-paper-50' : 'text-ink-500 hover:bg-paper-100 hover:text-ink-800'
                }`}
              >
                {option.label}
                <span className={`tnum ml-1.5 ${active ? 'text-paper-300' : 'text-ink-300'}`}>
                  {counts[option.key]}
                </span>
              </button>
            );
          })}
        </div>

        {subclaims.length > 1 ? (
          <label className="flex min-w-0 items-center gap-2 text-xs text-ink-500">
            <span className="shrink-0 uppercase tracking-[0.1em] text-ink-400">Subclaim</span>
            <select
              value={String(subclaimId)}
              onChange={(event) => {
                const next = event.target.value;
                setSubclaimId(next === 'all' ? 'all' : Number(next));
              }}
              // A select sizes itself to its widest option, so it is capped and
              // allowed to shrink; otherwise a long subclaim overflows the page.
              className="min-w-0 max-w-[11rem] truncate rounded-md border border-paper-300 bg-white px-2 py-1 text-xs text-ink-700 outline-none focus-visible:ring-2 focus-visible:ring-ink-800 sm:max-w-[16rem]"
            >
              <option value="all">All subclaims</option>
              {subclaims.map((sub, index) => (
                <option key={sub.id ?? sub.text} value={String(sub.id)} title={sub.text}>
                  {`${index + 1}. ${truncateLabel(sub.text, 34)}`}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>

      {visible.length === 0 ? (
        <EmptyNote>
          No evidence matches this filter.{' '}
          <button
            type="button"
            onClick={() => {
              setFilter('all');
              setSubclaimId('all');
            }}
            className="font-medium text-ink-700 underline underline-offset-4"
          >
            Clear filters
          </button>
        </EmptyNote>
      ) : (
        <>
          <ul className="space-y-2">
            {visible.map((item) => (
              <EvidenceCard
                key={item.id ?? `${item.document_id}-${item.subclaim_id}`}
                item={item}
                subclaimText={subclaims.find((sub) => sub.id === item.subclaim_id)?.text}
                independenceGroup={item.id != null ? groups?.[String(item.id)] : undefined}
              />
            ))}
          </ul>
          <p className="text-xs text-ink-400">
            Showing {visible.length} of {evidence.length}{' '}
            {pluralise(evidence.length, 'assessed document')}. Only documents compared against the claim
            on every specified dimension are counted as support.
          </p>
        </>
      )}
    </div>
  );
}

function EvidenceCard({
  item,
  subclaimText,
  independenceGroup,
}: {
  item: EvidenceItem;
  subclaimText?: string;
  independenceGroup?: number;
}) {
  const stance = stanceDescriptor(item.stance);
  const domain = publisherDomain(item);
  const title = item.title?.trim();
  const hasUrl = Boolean(item.url && /^https?:\/\//i.test(item.url));

  return (
    <li className="rounded-lg border border-paper-200 bg-white">
      <div className="flex">
        {/* Stance rail: the glyph beside it carries the same meaning as the colour. */}
        <span
          aria-hidden="true"
          className={`w-1 shrink-0 rounded-l-lg ${
            item.stance === 'supports'
              ? 'bg-emerald-500'
              : item.stance === 'contradicts'
                ? 'bg-rose-500'
                : item.stance === 'context'
                  ? 'bg-amber-400'
                  : 'bg-paper-300'
          }`}
        />

        <div className="min-w-0 flex-1 px-4 py-3.5 sm:px-5">
          <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
            <div className="min-w-0 flex-1">
              {hasUrl ? (
                <ExternalLink
                  href={item.url as string}
                  className="break-words font-serif text-base font-medium leading-snug no-underline hover:underline"
                >
                  <span className="hover:underline">{title || domain || 'Untitled source'}</span>
                </ExternalLink>
              ) : (
                <p className="break-words font-serif text-base font-medium leading-snug text-ink-900">
                  {title || 'Untitled source'}
                </p>
              )}

              <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 break-words text-xs text-ink-500">
                <span className="font-medium text-ink-600">{item.publisher?.trim() || 'Unknown publisher'}</span>
                {domain ? <span className="text-ink-300">·</span> : null}
                {domain ? <span>{domain}</span> : null}
                {item.published_at ? (
                  <>
                    <span className="text-ink-300">·</span>
                    <time dateTime={item.published_at}>{formatPublished(item.published_at)}</time>
                  </>
                ) : null}
                {item.retrieval_channel ? (
                  <>
                    <span className="text-ink-300">·</span>
                    <span>via {titleCase(item.retrieval_channel)}</span>
                  </>
                ) : null}
              </p>
            </div>

            <div className="flex shrink-0 flex-col items-end gap-1.5">
              <VerdictChip descriptor={stance} size="sm" />
              <span className="tnum text-2xs text-ink-400">{formatConfidence(item.confidence)}</span>
            </div>
          </div>

          {item.summary ? (
            <p className="mt-2.5 break-words text-sm leading-relaxed text-ink-700">{item.summary}</p>
          ) : null}

          {item.excerpt ? (
            <details className="mt-2.5 group">
              <summary className="cursor-pointer list-none text-xs font-medium text-ink-500 marker:hidden hover:text-ink-800">
                <span className="group-open:hidden">Show source excerpt</span>
                <span className="hidden group-open:inline">Hide source excerpt</span>
              </summary>
              <blockquote className="mt-2 break-words border-l-2 border-paper-300 pl-3 text-sm italic leading-relaxed text-ink-600">
                {item.excerpt}
              </blockquote>
            </details>
          ) : null}

          <dl className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-2xs text-ink-400">
            {subclaimText ? (
              <div className="flex min-w-0 gap-1.5">
                <dt className="shrink-0 uppercase tracking-[0.1em]">Compared against</dt>
                <dd className="truncate text-ink-600" title={subclaimText}>
                  {truncateLabel(subclaimText)}
                </dd>
              </div>
            ) : null}
            {item.category ? (
              <div className="flex gap-1.5">
                <dt className="uppercase tracking-[0.1em]">Kind</dt>
                <dd className="text-ink-600">{categoryLabel(item.category)}</dd>
              </div>
            ) : null}
            {item.assessment_status ? (
              <div className="flex gap-1.5">
                <dt className="uppercase tracking-[0.1em]">Status</dt>
                <dd className="text-ink-600">{assessmentStatusLabel(item.assessment_status)}</dd>
              </div>
            ) : null}
            {typeof independenceGroup === 'number' ? (
              <div className="flex gap-1.5">
                <dt className="uppercase tracking-[0.1em]">Independence group</dt>
                <dd className="tnum text-ink-600">#{independenceGroup}</dd>
              </div>
            ) : null}
          </dl>
        </div>
      </div>
    </li>
  );
}

function truncateLabel(value: string, max = 70): string {
  return value.length <= max ? value : `${value.slice(0, max - 1).trimEnd()}…`;
}

function formatPublished(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '';
  return parsed.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}
