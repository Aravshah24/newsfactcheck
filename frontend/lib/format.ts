import type { EvidenceCategory, Stance } from './types';

/**
 * Semantic tone used to pick colour. Every tone is always paired with a glyph
 * and a text label so meaning never depends on colour alone.
 */
export type Tone = 'positive' | 'negative' | 'caution' | 'neutral' | 'informative';

export interface Descriptor {
  label: string;
  glyph: string;
  tone: Tone;
  /** Border/background/text classes, kept as whole literals so Tailwind keeps them. */
  chip: string;
  accent: string;
  description: string;
}

const NEUTRAL_CHIP = 'border-stone-300 bg-stone-100 text-stone-700';

function descriptor(
  label: string,
  glyph: string,
  tone: Tone,
  accent: string,
  description: string,
  chip: string,
): Descriptor {
  return { label, glyph, tone, accent, description, chip };
}

/** Overall verdicts emitted by `InvestigationGraph._overall_verdict`. */
const OVERALL_VERDICTS: Record<string, Descriptor> = {
  SUPPORTED: descriptor(
    'Supported',
    '✓',
    'positive',
    'text-emerald-700',
    'Each subclaim has supporting evidence from independent sources, with no material contradictions.',
    'border-emerald-300 bg-emerald-50 text-emerald-800',
  ),
  DISPUTED: descriptor(
    'Contradicted',
    '✕',
    'negative',
    'text-rose-700',
    'The retrieved evidence conflicts with the claim on at least one compared dimension.',
    'border-rose-300 bg-rose-50 text-rose-800',
  ),
  PARTIALLY_SUPPORTED: descriptor(
    'Partially supported',
    '◐',
    'caution',
    'text-amber-700',
    'Some components of the claim are supported, but others are unconfirmed or contradicted.',
    'border-amber-300 bg-amber-50 text-amber-800',
  ),
  MISLEADING_OR_INCOMPLETE: descriptor(
    'Misleading / incomplete',
    '◑',
    'caution',
    'text-violet-700',
    'The claim may be partly accurate but omits qualifications needed to read it correctly.',
    'border-violet-300 bg-violet-50 text-violet-800',
  ),
  INSUFFICIENT_EVIDENCE: descriptor(
    'Insufficient evidence',
    '○',
    'neutral',
    'text-stone-600',
    'The evidence retrieved is too limited or too inconsistent to sustain a conclusion.',
    'border-stone-300 bg-stone-100 text-stone-700',
  ),
};

/** Per-subclaim verdicts, which the backend emits in lowercase. */
const SUBCLAIM_VERDICTS: Record<string, Descriptor> = {
  supported: OVERALL_VERDICTS.SUPPORTED,
  disputed: OVERALL_VERDICTS.DISPUTED,
  partially_supported: OVERALL_VERDICTS.PARTIALLY_SUPPORTED,
  misleading_or_incomplete: OVERALL_VERDICTS.MISLEADING_OR_INCOMPLETE,
  insufficient_evidence: OVERALL_VERDICTS.INSUFFICIENT_EVIDENCE,
  unverifiable: descriptor(
    'Unverifiable',
    '?',
    'neutral',
    'text-stone-600',
    'The subclaim could not be checked against the retrieved evidence.',
    'border-stone-300 bg-stone-100 text-stone-700',
  ),
};

const STANCES: Record<string, Descriptor> = {
  supports: descriptor(
    'Supports',
    '✓',
    'positive',
    'text-emerald-700',
    'The document entails the claim on every dimension the claim specifies.',
    'border-emerald-300 bg-emerald-50 text-emerald-800',
  ),
  contradicts: descriptor(
    'Contradicts',
    '✕',
    'negative',
    'text-rose-700',
    'The document conflicts with the claim on at least one compared dimension.',
    'border-rose-300 bg-rose-50 text-rose-800',
  ),
  context: descriptor(
    'Context only',
    '◐',
    'caution',
    'text-amber-700',
    'The document is related but does not entail the whole claim, so it cannot support it.',
    'border-amber-300 bg-amber-50 text-amber-800',
  ),
  neutral: descriptor(
    'Neutral',
    '–',
    'neutral',
    'text-stone-600',
    'The document was retrieved but does not speak to the claim directly.',
    'border-stone-300 bg-stone-100 text-stone-700',
  ),
  unknown: descriptor(
    'Not assessed',
    '?',
    'neutral',
    'text-stone-500',
    'The document could not be assessed against the claim.',
    'border-stone-300 bg-stone-100 text-stone-600',
  ),
};

const CATEGORIES: Record<string, string> = {
  raw: 'Raw source text',
  agent_interpretation: 'Agent assessment',
  verified_conclusion: 'Verified conclusion',
};

const COMPLETENESS: Record<string, Descriptor> = {
  COMPLETE: descriptor(
    'Complete',
    '✓',
    'positive',
    'text-emerald-700',
    'No material context was found to be missing.',
    'border-emerald-300 bg-emerald-50 text-emerald-800',
  ),
  MOSTLY_COMPLETE: descriptor(
    'Mostly complete',
    '◐',
    'caution',
    'text-amber-700',
    'Minor context appears to be missing.',
    'border-amber-300 bg-amber-50 text-amber-800',
  ),
  INCOMPLETE: descriptor(
    'Incomplete',
    '◑',
    'caution',
    'text-amber-700',
    'Meaningful context is missing from the claim as stated.',
    'border-amber-300 bg-amber-50 text-amber-800',
  ),
  MISLEADING_BY_OMISSION: descriptor(
    'Misleading by omission',
    '!',
    'negative',
    'text-rose-700',
    'The claim omits context that would change how a reader interprets it.',
    'border-rose-300 bg-rose-50 text-rose-800',
  ),
};

const PRIMARY_STATUS: Record<string, { label: string; note: string }> = {
  FOUND: { label: 'Primary sources found', note: 'Official or institutional records were retrieved.' },
  NOT_FOUND: { label: 'No primary sources', note: 'The primary-source channel ran but matched nothing.' },
  SEARCH_FAILED: { label: 'Primary search failed', note: 'The primary-source channel returned an error.' },
  NOT_CONFIGURED: { label: 'Primary source search not configured', note: 'No provider is configured for primary sources.' },
  NOT_SEARCHED: { label: 'Primary source search not run', note: 'The investigation did not reach primary search.' },
};

const CLAIM_STATUS: Record<string, string> = {
  draft: 'Draft',
  analyzing: 'Analysis recorded',
  verified: 'Investigation complete',
  archived: 'Archived',
};

const ASSESSMENT_STATUS: Record<string, string> = {
  unassessed: 'Not assessed against the claim',
  assessed: 'Assessed against the claim',
  verified: 'Carried into a verified conclusion',
  rejected: 'Rejected',
};

function lookup(table: Record<string, Descriptor>, value: string | null | undefined): Descriptor {
  const key = (value ?? '').trim();
  return table[key] ?? descriptor(titleCase(key) || 'Unknown', '?', 'neutral', 'text-stone-600', 'No description available.', NEUTRAL_CHIP);
}

export function overallVerdictDescriptor(value: string | null | undefined): Descriptor {
  return lookup(OVERALL_VERDICTS, value);
}

export function subclaimVerdictDescriptor(value: string | null | undefined): Descriptor {
  return lookup(SUBCLAIM_VERDICTS, value);
}

export function stanceDescriptor(value: string | null | undefined): Descriptor {
  return lookup(STANCES, value);
}

export function completenessDescriptor(value: string | null | undefined): Descriptor {
  return lookup(COMPLETENESS, value);
}

export function categoryLabel(value: string | null | undefined): string {
  const key = (value ?? '').trim();
  return CATEGORIES[key] ?? titleCase(key) ?? '';
}

export function assessmentStatusLabel(value: string | null | undefined): string {
  const key = (value ?? '').trim();
  return ASSESSMENT_STATUS[key] ?? titleCase(key);
}

export function primaryStatusLabel(value: string | null | undefined): { label: string; note: string } {
  const key = (value ?? '').trim();
  return (
    PRIMARY_STATUS[key] ?? {
      label: titleCase(key) || 'Unknown',
      note: 'The investigation did not report a primary-source status.',
    }
  );
}

export function claimStatusLabel(value: string | null | undefined): string {
  const key = (value ?? '').trim();
  return CLAIM_STATUS[key] ?? titleCase(key);
}

/** Stances that carry probative weight. Non-probative stances cannot support a verdict. */
export function isProbative(stance: string | null | undefined): boolean {
  const key = (stance ?? '').trim();
  return key === 'supports' || key === 'contradicts';
}

/** Human label for the rule that a guard rail applied, e.g. `single_independent_source`. */
export function ruleLabel(rule: string): string {
  return titleCase(rule.replace(/_/g, ' '));
}

export function titleCase(value: string | null | undefined): string {
  const text = (value ?? '').trim();
  if (!text) return '';
  return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
}

/** Formats a 0..1 confidence as a percentage, tolerating null and out-of-range input. */
export function formatConfidence(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  const clamped = Math.min(1, Math.max(0, value));
  return `${Math.round(clamped * 100)}%`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '';
  return parsed.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

export function pluralise(count: number, singular: string, plural?: string): string {
  return count === 1 ? singular : (plural ?? `${singular}s`);
}

export function truncate(value: string, max: number): string {
  return value.length <= max ? value : `${value.slice(0, max - 1).trimEnd()}…`;
}

/** Domain shown next to a publisher name when one is available. */
export function publisherDomain(item: { publisher_domain?: string | null }): string {
  const domain = item.publisher_domain?.trim();
  return domain ? domain.replace(/^www\./, '') : '';
}

export function isStance(value: string): value is Stance {
  return value in STANCES;
}

export function isCategory(value: string): value is EvidenceCategory {
  return value in CATEGORIES;
}
