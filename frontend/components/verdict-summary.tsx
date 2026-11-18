import {
  claimStatusLabel,
  formatConfidence,
  overallVerdictDescriptor,
  primaryStatusLabel,
  subclaimVerdictDescriptor,
} from '@/lib/format';
import type { InvestigationStateResponse } from '@/lib/types';
import { EmptyNote, Panel, VerdictChip } from './primitives';

export function VerdictSummary({ result }: { result: InvestigationStateResponse }) {
  const verdict = overallVerdictDescriptor(result.overall_verdict);
  const primary = primaryStatusLabel(result.primary_evidence_status);
  const hasVerdict = Boolean(result.overall_verdict);

  return (
    <Panel className="overflow-hidden shadow-md">
      <div className="grid gap-px bg-[#D1D5DB] sm:grid-cols-[1fr_auto]">
        <div className="bg-[#F9FAFB]/95 backdrop-blur-md px-5 py-5 sm:px-7 sm:py-6">
          <p className="label-micro">Verdict</p>
          <div className="mt-2.5 flex flex-wrap items-center gap-3">
            <h2 className={`font-serif text-3xl font-semibold leading-tight tracking-tight ${verdict.accent}`}>
              {verdict.label}
            </h2>
            <VerdictChip descriptor={verdict} size="sm" />
          </div>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-[#4B5563]">
            {result.overall_explanation ?? verdict.description}
          </p>
        </div>

        <dl className="grid grid-cols-2 gap-px bg-[#D1D5DB] sm:w-56 sm:grid-cols-1">
          <div className="bg-[#F9FAFB]/95 backdrop-blur-md px-5 py-3.5 sm:px-6">
            <dt className="label-micro">Confidence</dt>
            <dd className="mt-1 text-2xl font-semibold tnum text-[#111827]">
              {formatConfidence(result.overall_confidence)}
            </dd>
          </div>
          <div className="bg-[#F9FAFB]/95 backdrop-blur-md px-5 py-3.5 sm:px-6">
            <dt className="label-micro">Status</dt>
            <dd className="mt-1 text-sm font-medium leading-snug text-[#374151]">
              {claimStatusLabel(result.status)}
            </dd>
          </div>
        </dl>
      </div>

      {primaryStatusLabel(result.primary_evidence_status).label !== 'Unknown' ? (
        <div className="border-t border-[#D1D5DB] bg-[#E5E7EB]/90 px-5 py-3 sm:px-7">
          <p className="text-xs leading-relaxed text-[#4B5563]">
            <span className="font-semibold text-[#111827]">{primary.label}.</span> {primary.note}
          </p>
        </div>
      ) : null}

      {!hasVerdict ? (
        <div className="border-t border-[#D1D5DB] px-5 py-4 sm:px-7 bg-[#F9FAFB]/95">
          <EmptyNote>
            This investigation stored no overall verdict. The evidence sections below show what was
            retrieved, but nothing here should be read as a conclusion.
          </EmptyNote>
        </div>
      ) : null}

      <ReasoningNotice result={result} />
    </Panel>
  );
}

/**
 * Surfaces the constraint the system actually applied, so a verdict is never
 * presented as if the raw article count had produced it.
 */
function ReasoningNotice({ result }: { result: InvestigationStateResponse }) {
  const rules = Array.from(
    new Set(result.verification.flatMap((item) => item.applied_rules ?? [])),
  ).filter(Boolean);

  if (rules.length === 0) return null;

  return (
    <div className="border-t border-[#D1D5DB] bg-[#F9FAFB]/95 px-5 py-3.5 sm:px-7">
      <p className="label-micro">Constraints applied</p>
      <ul className="mt-2 flex flex-wrap gap-1.5">
        {rules.map((rule) => (
          <li
            key={rule}
            className="rounded border border-[#D1D5DB] bg-[#E5E7EB] px-2 py-0.5 text-2xs font-semibold text-[#1F2937]"
          >
            {rule.replace(/_/g, ' ')}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function VerificationList({ result }: { result: InvestigationStateResponse }) {
  if (result.verification.length === 0) {
    return (
      <EmptyNote>
        No per-subclaim conclusions were recorded. This happens when the run produced no usable
        evidence, or when the backend could not reach live reasoning.
      </EmptyNote>
    );
  }

  return (
    <ol className="space-y-3">
      {result.verification.map((item) => (
        <SubclaimCard
          key={item.subclaim_id ?? item.subclaim_text}
          item={item}
          evidence={result.evidence.filter((e) => e.subclaim_id === item.subclaim_id)}
        />
      ))}
    </ol>
  );
}

function SubclaimCard({
  item,
  evidence,
}: {
  item: InvestigationStateResponse['verification'][number];
  evidence: InvestigationStateResponse['evidence'];
}) {
  const display = subclaimVerdictDescriptor(item.verdict);

  return (
    <li className="rounded-xl border border-[#D1D5DB] bg-[#F9FAFB]/95 shadow-md backdrop-blur-md overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[#D1D5DB] bg-[#F3F4F6]/80 px-4 py-3.5 sm:px-5">
        <div className="min-w-0 flex-1">
          <p className="label-micro">Subclaim</p>
          <p className="mt-1.5 font-serif text-base font-medium leading-relaxed text-[#111827]">
            {item.subclaim_text ?? 'Untitled subclaim'}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <VerdictChip descriptor={display} size="sm" />
          <span className="tnum text-2xs font-medium text-[#6B7280]">{formatConfidence(item.confidence)} confidence</span>
        </div>
      </div>

      <div className="px-4 py-3.5 sm:px-5">
        {item.rationale ? (
          <p className="text-sm leading-relaxed text-[#4B5563]">{item.rationale}</p>
        ) : null}

        <dl className="mt-3.5 grid grid-cols-2 gap-x-4 gap-y-2.5 sm:grid-cols-4">
          <Tally label="Supports" value={item.supporting_evidence_count} />
          <Tally label="Contradicts" value={item.contradicting_evidence_count} />
          <Tally label="Context" value={item.context_evidence_count} />
          <Tally label="Independent groups" value={item.independent_supporting_groups} />
        </dl>

        {evidence.length > 0 ? (
          <p className="mt-3 text-2xs text-[#6B7280]">
            {evidence.length} {evidence.length === 1 ? 'document was' : 'documents were'} assessed against
            this subclaim.
          </p>
        ) : null}
      </div>
    </li>
  );
}

function Tally({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt className="text-2xs uppercase tracking-[0.1em] text-[#6B7280]">{label}</dt>
      <dd className="tnum mt-0.5 text-base font-semibold text-[#111827]">{value}</dd>
    </div>
  );
}
