'use client';

import Link from 'next/link';
import { LogoMark } from '@/components/primitives';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-transparent">
      <header className="border-b border-[#D1D5DB] bg-[#F3F4F6]/95 backdrop-blur-md sticky top-0 z-10">
        <div className="mx-auto flex max-w-[86rem] items-center justify-between gap-4 px-5 py-4 sm:px-8">
          <Link href="/" className="flex items-center gap-3" aria-label="FactTrace home">
            <LogoMark />
            <div>
              <p className="font-serif text-base font-semibold leading-none tracking-tight text-[#111827]">
                FactTrace
              </p>
              <p className="mt-1 text-2xs uppercase tracking-[0.14em] text-[#6B7280]">
                Evidence-backed claim investigation
              </p>
            </div>
          </Link>

          <nav className="hidden md:flex items-center gap-6">
            <Link
              href="#how-it-works"
              className="text-sm font-medium text-[#4B5563] transition hover:text-[#111827]"
            >
              How it works
            </Link>
            <Link
              href="/investigate"
              className="rounded-md bg-[#1F2937] px-4 py-2 text-sm font-semibold text-[#F9FAFB] transition hover:bg-[#111827]"
            >
              Investigate a claim
            </Link>
          </nav>

          <div className="md:hidden">
            <Link
              href="/investigate"
              className="rounded-md bg-[#1F2937] px-4 py-2 text-sm font-semibold text-[#F9FAFB] transition hover:bg-[#111827]"
            >
              Investigate a claim
            </Link>
          </div>
        </div>
      </header>

      <main className="bg-transparent">
        {/* Hero Section */}
        <section className="mx-auto max-w-[86rem] px-5 py-12 sm:px-8 sm:py-16 lg:py-20">
          <div className="mx-auto max-w-3xl text-center rounded-2xl border border-[#D1D5DB] bg-[#F3F4F6]/95 p-8 md:p-12 shadow-lg backdrop-blur-md">
            <p className="label-micro">Fact-checking with traceable evidence</p>
            <h1 className="mt-4 font-serif text-4xl font-semibold leading-[1.1] tracking-tight text-[#111827] sm:text-[3.25rem] lg:text-[3.75rem]">
              Trace the evidence behind any claim.
            </h1>
            <p className="mt-6 text-lg leading-relaxed text-[#4B5563]">
              Paste a claim. FactTrace decomposes it, retrieves sources across the web and official
              records, compares each document dimension by dimension, and weighs conclusions by
              source independence.
            </p>

            <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
              <Link
                href="/investigate"
                className="rounded-md bg-[#1F2937] px-6 py-3 text-base font-semibold text-[#F9FAFB] transition hover:bg-[#111827] focus-visible:ring-2 focus-visible:ring-[#1F2937] focus-visible:ring-offset-2 focus-visible:ring-offset-[#F3F4F6]"
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
                className="rounded-md border border-[#D1D5DB] bg-[#F9FAFB]/95 backdrop-blur-md px-6 py-3 text-base font-medium text-[#374151] transition hover:border-[#4B5563] hover:text-[#111827]"
              >
                See how it works
              </Link>
            </div>

            <div className="mt-12 relative" aria-hidden="true">
              <EvidenceTrailVisual />
            </div>
          </div>
        </section>

        {/* How it works */}
        <section id="how-it-works" className="mx-auto max-w-[86rem] px-5 py-12 sm:px-8 sm:py-16">
          <header className="mx-auto max-w-2xl text-center mb-10 rounded-2xl border border-[#D1D5DB] bg-[#F3F4F6]/95 p-6 md:p-8 shadow-md backdrop-blur-md">
            <p className="label-micro">How it works</p>
            <h2 className="mt-2 font-serif text-2xl font-semibold leading-snug tracking-tight text-[#111827] sm:text-3xl">
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

        {/* Core capabilities */}
        <section className="mx-auto max-w-[86rem] px-5 py-12 sm:px-8 sm:py-16">
          <header className="mx-auto max-w-2xl text-center mb-10 rounded-2xl border border-[#D1D5DB] bg-[#F3F4F6]/95 p-6 md:p-8 shadow-md backdrop-blur-md">
            <p className="label-micro">Core capabilities</p>
            <h2 className="mt-2 font-serif text-2xl font-semibold leading-snug tracking-tight text-[#111827] sm:text-3xl">
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

        {/* CTA section */}
        <section className="mx-auto max-w-4xl px-5 py-12 sm:px-8">
          <div className="rounded-2xl border border-[#D1D5DB] bg-[#1F2937] p-8 md:p-12 text-center text-[#F9FAFB] shadow-xl">
            <h2 className="font-serif text-2xl font-semibold leading-snug tracking-tight text-[#F9FAFB] sm:text-3xl">
              Ready to investigate a claim?
            </h2>
            <p className="mt-4 text-base leading-relaxed text-[#D1D5DB]">
              Paste a claim exactly as published. FactTrace will retrieve sources, evaluate the
              evidence, and return a verifiable report.
            </p>
            <div className="mt-8">
              <Link
                href="/investigate"
                className="inline-flex items-center gap-2 rounded-md bg-[#F9FAFB] px-6 py-3 text-base font-semibold text-[#111827] transition hover:bg-[#E5E7EB] focus-visible:ring-2 focus-visible:ring-[#F9FAFB] focus-visible:ring-offset-2 focus-visible:ring-offset-[#1F2937]"
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

      <footer className="border-t border-[#D1D5DB] bg-[#F3F4F6]/95 backdrop-blur-md px-5 py-8 sm:px-8">
        <div className="mx-auto flex max-w-[86rem] flex-wrap items-center justify-between gap-4 text-2xs text-[#6B7280]">
          <p>
            FactTrace — Evidence-backed claim investigation. Verdicts are research aids, not
            calibrated truth.
          </p>
          <nav className="flex flex-wrap items-center gap-4">
            <Link href="/investigate" className="underline underline-offset-2 hover:text-[#111827]">
              Investigate
            </Link>
            <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-[#111827]">
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
    <article className="relative rounded-2xl border border-[#D1D5DB] bg-[#F9FAFB]/95 backdrop-blur-md p-6 shadow-md">
      <span className="absolute -top-3 left-4 z-10 rounded-full border border-[#D1D5DB] bg-[#E5E7EB] px-2.5 py-0.5 text-2xs font-semibold uppercase tracking-[0.12em] text-[#374151]">
        Step {number}
      </span>
      <h3 className="mt-2 font-serif text-lg font-semibold leading-snug text-[#111827]">{title}</h3>
      <p className="mt-3 text-sm leading-relaxed text-[#4B5563]">{description}</p>
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
    <article className="rounded-2xl border border-[#D1D5DB] bg-[#F9FAFB]/95 backdrop-blur-md p-6 shadow-md">
      <h3 className="font-serif text-base font-semibold leading-snug text-[#111827]">{title}</h3>
      <p className="mt-2.5 text-sm leading-relaxed text-[#4B5563]">{description}</p>
    </article>
  );
}

function EvidenceTrailVisual() {
  // A subtle evidence-trail motif: connected nodes with varying opacity,
  // suggesting a chain of documents leading to a conclusion.
  return (
    <svg
      viewBox="0 0 400 200"
      className="mx-auto max-w-[32rem] h-auto opacity-75"
      aria-hidden="true"
      role="img"
      aria-label="Evidence trail visualisation"
    >
      <defs>
        <linearGradient id="trailGradient" x1="0%" y1="50%" x2="100%" y2="50%">
          <stop offset="0%" stopColor="#111827" stopOpacity="0.2" />
          <stop offset="50%" stopColor="#111827" stopOpacity="0.45" />
          <stop offset="100%" stopColor="#111827" stopOpacity="0.75" />
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
      <circle cx="40" cy="100" r="4" fill="#111827" opacity="0.3" />
      <circle cx="100" cy="60" r="5" fill="#111827" opacity="0.4" />
      <circle cx="160" cy="100" r="6" fill="#111827" opacity="0.5" />
      <circle cx="220" cy="140" r="5" fill="#111827" opacity="0.45" />
      <circle cx="280" cy="100" r="7" fill="#111827" opacity="0.6" />
      <circle cx="340" cy="60" r="5" fill="#111827" opacity="0.45" />
      <circle cx="360" cy="100" r="8" fill="#111827" opacity="0.85" />

      {/* Small satellites around key nodes */}
      <circle cx="160" cy="100" r="14" fill="none" stroke="#111827" strokeWidth="0.5" opacity="0.2" />
      <circle cx="280" cy="100" r="18" fill="none" stroke="#111827" strokeWidth="0.5" opacity="0.2" />
      <circle cx="360" cy="100" r="22" fill="none" stroke="#111827" strokeWidth="0.5" opacity="0.2" />
    </svg>
  );
}
