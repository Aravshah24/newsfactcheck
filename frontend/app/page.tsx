'use client';

import Link from 'next/link';
import { LogoMark } from '@/components/primitives';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-paper-50">
      <header className="border-b border-paper-200 bg-paper-100/60 sticky top-0 z-10">
        <div className="mx-auto flex max-w-[86rem] items-center justify-between gap-4 px-5 py-4 sm:px-8">
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

          <nav className="hidden md:flex items-center gap-6">
            <Link
              href="#how-it-works"
              className="text-sm font-medium text-ink-600 transition hover:text-ink-900"
            >
              How it works
            </Link>
            <Link
              href="/investigate"
              className="rounded-md bg-ink-900 px-4 py-2 text-sm font-semibold text-paper-50 transition hover:bg-ink-700"
            >
              Investigate a claim
            </Link>
          </nav>

          <div className="md:hidden">
            <Link
              href="/investigate"
              className="rounded-md bg-ink-900 px-4 py-2 text-sm font-semibold text-paper-50 transition hover:bg-ink-700"
            >
              Investigate a claim
            </Link>
          </div>
        </div>
      </header>

      <main>
        <section className="mx-auto max-w-[86rem] px-5 py-16 sm:px-8 sm:py-24 lg:py-28">
          <div className="mx-auto max-w-3xl text-center">
            <p className="label-micro">Fact-checking with traceable evidence</p>
            <h1 className="mt-4 font-serif text-4xl font-semibold leading-[1.1] tracking-tight text-ink-900 sm:text-[3.5rem] lg:text-[4rem]">
              Trace the evidence behind any claim.
            </h1>
            <p className="mt-6 text-lg leading-relaxed text-ink-600">
              Paste a claim. FactTrace decomposes it, retrieves sources across the web and official
              records, compares each document dimension by dimension, and weighs conclusions by
              source independence.
            </p>

            <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
              <Link
                href="/investigate"
                className="rounded-md bg-ink-900 px-6 py-3 text-base font-semibold text-paper-50 transition hover:bg-ink-700 focus-visible:ring-2 focus-visible:ring-ink-800 focus-visible:ring-offset-2 focus-visible:ring-offset-paper-50"
              >
                Investigate a claim
                <svg
                  aria-hidden="true"
                  viewBox="0 0 16 16"
                  className="ml-2 inline-block h-4 w-4 shrink-0"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M3 8h10" />
                  <path d="M9 4l4 4-4 4" />
                </svg>
              </Link>
              <Link
                href="#how-it-works"
                className="rounded-md border border-paper-300 bg-white px-6 py-3 text-base font-medium text-ink-700 transition hover:border-ink-400 hover:text-ink-900"
              >
                See how it works
              </Link>
            </div>

            <div className="mt-16 relative" aria-hidden="true">
              <EvidenceTrailVisual />
            </div>
          </div>
        </section>

        <section id="how-it-works" className="mx-auto max-w-[86rem] px-5 py-12 sm:px-8 sm:py-16">
          <header className="mx-auto max-w-2xl text-center mb-16">
            <p className="label-micro">How it works</p>
            <h2 className="mt-3 font-serif text-2xl font-semibold leading-snug tracking-tight text-ink-900 sm:text-3xl">
              From claim to verifiable conclusion in four steps.
            </h2>
          </header>

          <div className="mx-auto max-w-[86rem] grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            <StepCard
              number="01"
              title="Claim analysis"
              description="The claim is split into atomic, independently checkable subclaims. Each part is decomposed into comparable dimensions — subject, action, object, location, date, quantity, polarity."
            />
            <StepCard
              number="02"
              title="Multi-source retrieval"
              description="Parallel searches run across GDELT, web search, and official-domain channels. Results are deduplicated at ingestion so syndicated copies never inflate confidence."
            />
            <StepCard
              number="03"
              title="Evidence evaluation"
              description="Every document is compared against the complete proposition, not just its topic. Each dimension is judged as match, conflict, absent, or unclear. Any conflict forces a contradiction verdict."
            />
            <StepCard
              number="04"
              title="Report generation"
              description="Conclusions are weighed by independent source groups. The report includes completeness analysis, media-coverage framing, and a full evidence trace with per-dimension reasoning."
            />
          </div>
        </section>

        <section className="mx-auto max-w-[86rem] px-5 py-16 sm:px-8 sm:py-24 bg-paper-100/50">
          <header className="mx-auto max-w-2xl text-center mb-16">
            <p className="label-micro">Core capabilities</p>
            <h2 className="mt-3 font-serif text-2xl font-semibold leading-snug tracking-tight text-ink-900 sm:text-3xl">
              Built for rigorous, transparent investigation.
            </h2>
          </header>

          <div className="mx-auto max-w-[86rem] grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
            <CapabilityCard
              title="Evidence traceability"
              description="Every verdict links back to specific documents, with per-dimension match/conflict reasoning shown inline. Nothing is asserted without a source."
            />
            <CapabilityCard
              title="Supporting & contradicting evidence"
              description="Documents are classified as supports, contradicts, context, or neutral. Context and neutral items never raise confidence — only full entailment does."
            />
            <CapabilityCard
              title="Source independence analysis"
              description="Documents are grouped by publisher, content hash, and republication chains. Confidence is capped by the number of independent groups, not raw document count."
            />
            <CapabilityCard
              title="Uncertainty-aware verdicts"
              description="Verdicts are Supported, Partially Supported, Disputed, Misleading or Incomplete, Unverifiable, or Insufficient Evidence. Confidence reflects independent corroboration, not model certainty."
            />
            <CapabilityCard
              title="Media & political-leaning analysis"
              description="Coverage is summarised by publisher distribution and editorial lean (left/center/right/unknown). Lean is contextual framing — never evidence for or against a claim."
            />
            <CapabilityCard
              title="Primary-source channel"
              description="A dedicated search targets official domains (.gov, courts, statistics bodies) and fetches full page text so official records are adjudicated on their body, not a snippet."
            />
          </div>
        </section>

        <section className="mx-auto max-w-[86rem] px-5 py-16 sm:px-8 sm:py-24 bg-ink-900">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="font-serif text-2xl font-semibold leading-snug tracking-tight text-paper-50 sm:text-3xl">
              Ready to investigate a claim?
            </h2>
            <p className="mt-4 text-base leading-relaxed text-paper-50">
              Paste a claim exactly as published. FactTrace will retrieve sources, evaluate the
              evidence, and return a verifiable report.
            </p>
            <div className="mt-8">
              <Link
                href="/investigate"
                className="inline-flex items-center gap-2 rounded-md bg-paper-50 px-6 py-3 text-base font-semibold text-ink-900 transition hover:bg-paper-100 focus-visible:ring-2 focus-visible:ring-paper-50 focus-visible:ring-offset-2 focus-visible:ring-offset-ink-900"
              >
                Start an investigation
                <svg
                  aria-hidden="true"
                  viewBox="0 0 16 16"
                  className="h-4 w-4 shrink-0"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M3 8h10" />
                  <path d="M9 4l4 4-4 4" />
                </svg>
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-paper-200 bg-paper-100/60 px-5 py-10 sm:px-8">
        <div className="mx-auto flex max-w-[86rem] flex-wrap items-center justify-between gap-4 text-2xs text-ink-400">
          <p>
            FactTrace — Evidence-backed claim investigation. Verdicts are research aids, not
            calibrated truth.
          </p>
          <nav className="flex flex-wrap items-center gap-4">
            <Link href="/investigate" className="underline underline-offset-2 hover:text-ink-700">
              Investigate
            </Link>
            <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-ink-700">
              GitHub
            </a>
          </nav>
        </div>
      </footer>
    </div>
  );
}

function StepCard({
  number,
  title,
  description,
}: {
  number: string;
  title: string;
  description: string;
}) {
  return (
    <article className="relative rounded-lg border border-paper-200 bg-white p-6">
      <span className="absolute -top-3 left-4 z-10 rounded-full bg-paper-50 px-2.5 py-0.5 text-2xs font-semibold uppercase tracking-[0.12em] text-ink-500">
        Step {number}
      </span>
      <h3 className="mt-2 font-serif text-lg font-semibold leading-snug text-ink-900">{title}</h3>
      <p className="mt-3 text-sm leading-relaxed text-ink-600">{description}</p>
    </article>
  );
}

function CapabilityCard({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <article className="rounded-lg border border-paper-200 bg-white p-6">
      <h3 className="font-serif text-base font-semibold leading-snug text-ink-900">{title}</h3>
      <p className="mt-2.5 text-sm leading-relaxed text-ink-600">{description}</p>
    </article>
  );
}

function EvidenceTrailVisual() {
  // A subtle evidence-trail motif: connected nodes with varying opacity,
  // suggesting a chain of documents leading to a conclusion.
  return (
    <svg
      viewBox="0 0 400 200"
      className="mx-auto max-w-[32rem] h-auto opacity-60"
      aria-hidden="true"
      role="img"
      aria-label="Evidence trail visualisation"
    >
      <defs>
        <linearGradient id="trailGradient" x1="0%" y1="50%" x2="100%" y2="50%">
          <stop offset="0%" stopColor="#211f1c" stopOpacity="0.15" />
          <stop offset="50%" stopColor="#211f1c" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#211f1c" stopOpacity="0.6" />
        </linearGradient>
      </defs>

      {/* Connecting trail */}
      <path
        d="M40,100 Q100,60 160,100 Q220,140 280,100 Q340,60 360,100"
        fill="none"
        stroke="url(#trailGradient)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Nodes - varying sizes and opacities */}
      <circle cx="40" cy="100" r="4" fill="#211f1c" opacity="0.2" />
      <circle cx="100" cy="60" r="5" fill="#211f1c" opacity="0.3" />
      <circle cx="160" cy="100" r="6" fill="#211f1c" opacity="0.4" />
      <circle cx="220" cy="140" r="5" fill="#211f1c" opacity="0.35" />
      <circle cx="280" cy="100" r="7" fill="#211f1c" opacity="0.5" />
      <circle cx="340" cy="60" r="5" fill="#211f1c" opacity="0.35" />
      <circle cx="360" cy="100" r="8" fill="#211f1c" opacity="0.7" />

      {/* Small satellites around key nodes */}
      <circle cx="160" cy="100" r="14" fill="none" stroke="#211f1c" strokeWidth="0.5" opacity="0.15" />
      <circle cx="280" cy="100" r="18" fill="none" stroke="#211f1c" strokeWidth="0.5" opacity="0.15" />
      <circle cx="360" cy="100" r="22" fill="none" stroke="#211f1c" strokeWidth="0.5" opacity="0.15" />
    </svg>
  );
}