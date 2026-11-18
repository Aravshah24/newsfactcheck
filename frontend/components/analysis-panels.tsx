import { completenessDescriptor, formatConfidence, pluralise } from '@/lib/format';
import type { CompletenessSummary, MediaCoverage, SourceIndependence } from '@/lib/types';
import { BulletList, EmptyNote, Panel, VerdictChip } from './primitives';

/**
 * Independence is what stops ten syndicated copies of one wire story from
 * reading as ten confirmations, so this section leads with the plain-language
 * sentence and keeps the raw counts secondary.
 */
export function SourceIndependence({ data }: { data: SourceIndependence | null }) {
  if (!data) {
    return <EmptyNote>The investigation did not record a source-independence analysis.</EmptyNote>;
  }

  const groups = data.groups ?? [];
  const maxSize = groups.reduce((max, group) => Math.max(max, group.document_count), 0);

  return (
    <Panel className="p-5 shadow-md">
      <p className="text-sm leading-relaxed text-[#374151]">
        <span className="font-bold text-[#111827] tnum">{data.documents_found}</span>{' '}
        {pluralise(data.documents_found, 'document')} from{' '}
        <span className="font-bold text-[#111827] tnum">{data.distinct_publishers}</span>{' '}
        {pluralise(data.distinct_publishers, 'publisher')}, grouped into{' '}
        <span className="font-bold text-[#111827] tnum">{data.independent_groups}</span>{' '}
        {pluralise(data.independent_groups, 'independent group')}.
      </p>

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-[#D1D5DB] pt-4">
        <Metric label="Independent sources" value={data.estimated_independent_sources} />
        <Metric label="Evidence clusters" value={data.evidence_clusters} />
        <Metric label="Duplicate / derived" value={data.duplicate_derived_documents} />
        <Metric label="Dependency edges" value={data.dependency_edges} />
      </dl>

      {groups.length > 0 ? (
        <div className="mt-4 border-t border-[#D1D5DB] pt-4">
          <p className="label-micro mb-2.5">Group sizes</p>
          <ul className="space-y-1.5">
            {groups.slice(0, 8).map((group) => (
              <li key={group.group_id} className="flex items-center gap-2.5">
                <span className="tnum w-8 shrink-0 text-2xs font-semibold text-[#6B7280]">#{group.group_id}</span>
                <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#E5E7EB] border border-[#D1D5DB]/40">
                  <span
                    className="block h-full rounded-full bg-[#1F2937]"
                    style={{ width: `${maxSize > 0 ? (group.document_count / maxSize) * 100 : 0}%` }}
                  />
                </span>
                <span className="tnum w-6 shrink-0 text-right text-2xs font-semibold text-[#4B5563]">
                  {group.document_count}
                </span>
                <span className="min-w-0 flex-1 truncate text-2xs text-[#6B7280]">
                  {(group.publishers ?? []).join(', ')}
                </span>
              </li>
            ))}
          </ul>
          {groups.length > 8 ? (
            <p className="mt-2 text-2xs text-[#6B7280]">and {groups.length - 8} more groups</p>
          ) : null}
        </div>
      ) : null}
    </Panel>
  );
}

function Metric({ label, value }: { label: string; value: number | null | undefined }) {
  return (
    <div>
      <dt className="text-2xs font-bold uppercase tracking-[0.1em] text-[#6B7280]">{label}</dt>
      <dd className="tnum mt-0.5 text-base font-bold text-[#111827]">{value ?? '—'}</dd>
    </div>
  );
}

export function Completeness({ data }: { data: CompletenessSummary | null }) {
  if (!data) {
    return <EmptyNote>The investigation did not record a completeness assessment.</EmptyNote>;
  }

  const descriptor = completenessDescriptor(data.completeness_status);

  return (
    <Panel className="p-5 shadow-md">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <VerdictChip descriptor={descriptor} />
        <span className="tnum text-2xs font-semibold text-[#6B7280]">
          {formatConfidence(data.confidence)} confidence
        </span>
      </div>
      <p className="mt-2.5 text-xs leading-relaxed text-[#4B5563]">{descriptor.description}</p>

      {data.missing_context && data.missing_context.length > 0 ? (
        <div className="mt-4 border-t border-[#D1D5DB] pt-3.5">
          <p className="label-micro mb-2">Missing context</p>
          <BulletList items={data.missing_context} />
        </div>
      ) : null}

      {data.qualifications && data.qualifications.length > 0 ? (
        <div className="mt-4 border-t border-[#D1D5DB] pt-3.5">
          <p className="label-micro mb-2">Qualifications a reader needs</p>
          <BulletList items={data.qualifications} />
        </div>
      ) : null}

      {!data.missing_context?.length && !data.qualifications?.length ? (
        <p className="mt-3.5 text-xs leading-relaxed text-[#6B7280]">
          No specific omissions were identified in this run.
        </p>
      ) : null}
    </Panel>
  );
}

/**
 * Media coverage describes who reported the claim, not whether it is true. The
 * framing copy and the heading both say so explicitly.
 */
export function MediaCoveragePanel({ data }: { data: MediaCoverage | null }) {
  if (!data) {
    return <EmptyNote>The investigation did not record a media-coverage analysis.</EmptyNote>;
  }

  const distribution = Object.entries(data.publisher_distribution ?? {})
    .filter(([, count]) => typeof count === 'number' && Number.isFinite(count))
    .sort((a, b) => b[1] - a[1]);

  const total = distribution.reduce((sum, [, count]) => sum + count, 0);
  const omitted = normaliseOmitted(data.omitted_context);

  return (
    <Panel className="p-5 shadow-md">
      <p className="rounded-lg border border-[#D1D5DB] bg-[#E5E7EB]/90 px-3 py-2 text-xs font-medium leading-relaxed text-[#374151]">
        This section describes who covered the claim. Coverage is not evidence for or against it.
      </p>

      {data.framing_summary ? (
        <p className="mt-3.5 text-sm leading-relaxed text-[#374151]">{data.framing_summary}</p>
      ) : null}

      <LeanCoverage data={data} />

      {distribution.length > 0 ? (
        <div className="mt-4 border-t border-[#D1D5DB] pt-4">
          <p className="label-micro mb-2.5">Publisher distribution</p>
          <ul className="space-y-1.5">
            {distribution.slice(0, 10).map(([publisher, count]) => (
              <li key={publisher} className="flex items-center gap-2.5">
                <span className="min-w-0 flex-1 truncate text-xs font-medium text-[#374151]" title={publisher}>
                  {publisher}
                </span>
                <span className="h-1.5 w-16 shrink-0 overflow-hidden rounded-full bg-[#E5E7EB] border border-[#D1D5DB]/40">
                  <span
                    className="block h-full rounded-full bg-[#1F2937]"
                    style={{ width: `${total > 0 ? (count / total) * 100 : 0}%` }}
                  />
                </span>
                <span className="tnum w-5 shrink-0 text-right text-2xs font-semibold text-[#6B7280]">{count}</span>
              </li>
            ))}
          </ul>
          {distribution.length > 10 ? (
            <p className="mt-2 text-2xs text-[#6B7280]">and {distribution.length - 10} more publishers</p>
          ) : null}
        </div>
      ) : null}

      {omitted.length > 0 ? (
        <div className="mt-4 border-t border-[#D1D5DB] pt-4">
          <p className="label-micro mb-2">Noted as omitted</p>
          <BulletList items={omitted} />
        </div>
      ) : null}

      {data.methodology ? (
        <p className="mt-4 border-t border-[#D1D5DB] pt-3.5 text-2xs leading-relaxed text-[#6B7280]">
          {data.methodology}
        </p>
      ) : null}
    </Panel>
  );
}

/** The backend decodes this field from JSON, so it may be a list or a raw string. */
function normaliseOmitted(value: MediaCoverage['omitted_context']): string[] {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter((entry): entry is string => typeof entry === 'string');
  if (typeof value === 'string' && value.trim()) return [value.trim()];
  return [];
}

/**
 * Editorial-lean distribution of the retrieved corpus. The shares are fractions
 * of the corpus (left/center/right/unknown sum to 1); the reviewer sourcing is
 * stated in the methodology line below. Lean is coverage, never evidence.
 */
function LeanCoverage({ data }: { data: MediaCoverage }) {
  const rows = [
    { label: 'Left', value: data.left_coverage },
    { label: 'Center', value: data.center_coverage },
    { label: 'Right', value: data.right_coverage },
    { label: 'Unknown', value: data.unknown_coverage },
  ];
  const hasAny = rows.some((row) => typeof row.value === 'number' && row.value > 0);
  if (!hasAny) return null;

  const percentage = (value: number | null | undefined) =>
    typeof value === 'number' ? Math.min(100, Math.max(0, Math.round(value * 100))) : 0;

  return (
    <div className="mt-4 border-t border-[#D1D5DB] pt-4">
      <p className="label-micro mb-2.5">Coverage by editorial lean</p>
      <ul className="space-y-1.5">
        {rows.map((row) => {
          const pct = percentage(row.value);
          return (
            <li key={row.label} className="flex items-center gap-2.5">
              <span className="w-16 shrink-0 text-xs font-medium text-[#374151]">{row.label}</span>
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#E5E7EB] border border-[#D1D5DB]/40">
                <span
                  className={`block h-full rounded-full ${row.label === 'Unknown' ? 'bg-[#9CA3AF]' : 'bg-[#1F2937]'}`}
                  style={{ width: `${pct}%` }}
                />
              </span>
              <span className="tnum w-9 shrink-0 text-right text-2xs font-semibold text-[#6B7280]">{pct}%</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
