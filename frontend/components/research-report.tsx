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
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-ink-400">
                {block.heading}
              </h3>
            ) : null}
            <p className="report-prose">{block.body}</p>
          </section>
        ))}
      </article>

      {sources.length > 0 ? (
        <div className="mt-7 border-t border-paper-200 pt-5">
          <p className="label-micro mb-3">Sources behind this report</p>
          <ul className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
            {sources.slice(0, 24).map((source) => (
              <li key={source.url} className="min-w-0 text-sm">
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-baseline gap-1.5 text-ink-600 transition hover:text-ink-900"
                >
                  <span aria-hidden="true" className="shrink-0 text-ink-300">
                    ↗
                  </span>
                  <span className="truncate underline decoration-paper-300 underline-offset-4 hover:decoration-ink-400">
                    {source.label}
                  </span>
                </a>
              </li>
            ))}
          </ul>
          {sources.length > 24 ? (
            <p className="mt-2.5 text-2xs text-ink-400">and {sources.length - 24} more sources</p>
          ) : null}
        </div>
      ) : null}
    </Panel>
  );
}

function uniqueSources(evidence: EvidenceItem[]): { label: string; url: string }[] {
  const seen = new Map<string, string>();
  for (const item of evidence) {
    if (!item.url || !/^https?:\/\//i.test(item.url)) continue;
    if (seen.has(item.url)) continue;
    const domain = item.publisher?.trim() || hostOf(item.url);
    const title = item.title?.trim();
    seen.set(item.url, title ? `${title} — ${domain}` : domain);
  }
  return Array.from(seen, ([url, label]) => ({ label, url }));
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}
