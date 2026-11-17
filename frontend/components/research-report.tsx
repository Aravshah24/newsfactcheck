import type { EvidenceItem } from '@/lib/types';
import { EmptyNote, Panel } from './primitives';

const HEADING = /^[A-Z][A-Z \-/&]{3,}$/;
const RULE = /^-{3,}$/;

/**
 * Renders the backend's report text as readable prose.
 *
 * The writer agent emits section headings in capitals and rules between them,
 * so those are promoted to real headings instead of being left as raw markup.
 */
function renderReport(text: string): { heading: string | null; body: string }[] {
  const lines = text.split(/\r?\n/);
  const blocks: { heading: string | null; body: string }[] = [];
  let heading: string | null = null;
  let buffer: string[] = [];

  const flush = () => {
    const body = buffer.join('\n').trim();
    if (body) blocks.push({ heading, body });
    buffer = [];
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (RULE.test(trimmed)) {
      flush();
      continue;
    }
    if (trimmed && HEADING.test(trimmed) && trimmed.length < 60) {
      flush();
      heading = trimmed;
      continue;
    }
    buffer.push(line);
  }
  flush();

  return blocks.length > 0 ? blocks : [{ heading: null, body: text.trim() }];
}

export function ResearchReport({
  report,
  evidence,
}: {
  report: string | null;
  evidence: EvidenceItem[];
}) {
  if (!report || !report.trim()) {
    return (
      <EmptyNote>
        No report text was produced for this investigation. The sections above still show everything
        the run recorded.
      </EmptyNote>
    );
  }

  const blocks = renderReport(report);
  // Collect the distinct real sources the report's run touched, so the
  // conclusion is followed by the links it rests on.
  const sources = uniqueSources(evidence);

  return (
    <Panel className="p-5 sm:p-7">
      <article className="max-w-2xl">
        {blocks.map((block, index) => (
          <section key={index} className={index > 0 ? 'mt-6' : undefined}>
            {block.heading ? (
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#6B7280]">
                {block.heading}
              </h3>
            ) : null}
            <p className="report-prose">{block.body}</p>
          </section>
        ))}
      </article>

      {sources.length > 0 ? (
        <div className="mt-7 border-t border-[#D1D5DB] pt-5">
          <p className="label-micro mb-3">Sources behind this report</p>
          <ul className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
            {sources.slice(0, 24).map((source) => (
              <li key={source.url} className="min-w-0 text-sm">
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-baseline gap-1.5 text-[#4B5563] transition hover:text-[#111827]"
                >
                  <span aria-hidden="true" className="shrink-0 text-[#9CA3AF]">
                    ↗
                  </span>
                  <span className="truncate underline decoration-[#D1D5DB] underline-offset-4 hover:decoration-[#4B5563]">
                    {source.label}
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Panel>
  );
}

function uniqueSources(evidence: EvidenceItem[]): { url: string; label: string }[] {
  const seen = new Set<string>();
  const out: { url: string; label: string }[] = [];

  for (const item of evidence) {
    const url = item.url?.trim();
    if (!url || !/^https?:\/\//i.test(url)) continue;
    if (seen.has(url)) continue;
    seen.add(url);

    const label =
      item.title?.trim() ||
      item.publisher?.trim() ||
      url.replace(/^https?:\/\/(?:www\.)?/, '').split('/')[0] ||
      url;

    out.push({ url, label });
  }

  return out;
}
