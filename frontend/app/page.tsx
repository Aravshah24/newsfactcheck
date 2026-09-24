"use client";

import { FormEvent, useMemo, useState } from "react";

const DEFAULT_CLAIM = "The city reduced traffic by 20% after the new lane opened.";

export default function Home() {
  const [claim, setClaim] = useState(DEFAULT_CLAIM);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const apiBase = useMemo(() => process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000", []);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const createResponse = await fetch(`${apiBase}/api/v1/investigations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ claim }),
      });

      const created = await createResponse.json();
      if (!createResponse.ok) {
        throw new Error(created.detail || "Investigation failed");
      }

      const fetchResponse = await fetch(`${apiBase}/api/v1/investigations/${created.claim_id}`);
      const payload = await fetchResponse.json();
      setResult(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit claim");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <div className="mb-8 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-cyan-400">News Fact Checker</p>
            <h1 className="mt-2 text-4xl font-bold">Evidence-based claim investigation</h1>
          </div>
          <div className="rounded-full border border-amber-400/40 bg-amber-500/10 px-4 py-2 text-xs text-amber-300">
            Demo mode – using fixture evidence.
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mb-8 rounded-2xl border border-slate-800 bg-slate-900 p-6">
          <label className="mb-3 block text-sm font-medium text-slate-200">Enter a news claim</label>
          <textarea
            value={claim}
            onChange={(event) => setClaim(event.target.value)}
            rows={4}
            className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 outline-none ring-0 placeholder:text-slate-500"
            placeholder="Example: The city reduced traffic by 20% after the new lane opened."
          />
          <div className="mt-4 flex items-center gap-3">
            <button
              type="submit"
              disabled={loading}
              className="rounded-xl bg-cyan-500 px-5 py-3 font-medium text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "Investigating..." : "Investigate"}
            </button>
          </div>
        </form>

        {error && <div className="mb-6 rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-red-200">{error}</div>}

        {result && (
          <div className="space-y-8">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
              <div className="mb-4 flex items-center justify-between gap-4">
                <h2 className="text-2xl font-semibold">Overall verdict</h2>
                <span className="rounded-full border border-cyan-500/40 bg-cyan-500/10 px-3 py-1 text-sm text-cyan-300">
                  {result.overall_verdict || "UNKNOWN"}
                </span>
              </div>
              <p className="text-sm text-slate-300">Confidence: {result.overall_confidence ?? "0.00"}</p>
              <p className="mt-3 text-slate-200">{result.report ? result.report.split("SUMMARY")[0] : "No summary available."}</p>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
                <h3 className="mb-3 text-xl font-semibold">Subclaims</h3>
                <ul className="space-y-3 text-sm text-slate-200">
                  {result.subclaims?.map((subclaim: any) => (
                    <li key={subclaim.id} className="rounded-lg border border-slate-800 bg-slate-950 p-3">
                      <p className="font-medium">{subclaim.text}</p>
                      <p className="mt-1 text-xs uppercase tracking-wide text-slate-400">{subclaim.type}</p>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
                <h3 className="mb-3 text-xl font-semibold">Missing context</h3>
                <ul className="space-y-2 text-sm text-slate-200">
                  {(result.completeness?.missing_context || ["No major missing-context issues identified."]).map((item: string, index: number) => (
                    <li key={index} className="rounded-lg border border-slate-800 bg-slate-950 p-3">{item}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
              <h3 className="mb-3 text-xl font-semibold">Source independence</h3>
              <pre className="whitespace-pre-wrap text-sm text-slate-200">{JSON.stringify(result.source_independence || {}, null, 2)}</pre>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
              <h3 className="mb-3 text-xl font-semibold">Media coverage</h3>
              <pre className="whitespace-pre-wrap text-sm text-slate-200">{JSON.stringify(result.media_coverage || {}, null, 2)}</pre>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
              <h3 className="mb-3 text-xl font-semibold">Full report</h3>
              <pre className="whitespace-pre-wrap text-sm text-slate-200">{result.report || "No report generated."}</pre>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
