"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getIndustries, type Industry } from "@/lib/api";
import { hasAnswers, useSession } from "@/lib/session";
import { ErrorPanel, LoadingPanel } from "@/components/StatePanels";
import { Eyebrow } from "@/components/ui";

/**
 * The screen where a prospect decides whether this was built for them. Each
 * card names that industry's actual risks in its own vocabulary, never generic
 * categories, and never another industry's models.
 */
export default function StartPage() {
  const router = useRouter();
  const { industry, setIndustry } = useSession();
  const [industries, setIndustries] = useState<Industry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<Industry | null>(null);

  useEffect(() => {
    getIndustries()
      .then((r) => setIndustries(r.industries))
      .catch((e) => setError(e.message));
  }, []);

  const choose = (pack: Industry) => {
    // Changing industry discards intake, so say so before doing it.
    if (industry && industry !== pack.id && hasAnswers()) {
      setConfirming(pack);
      return;
    }
    setIndustry(pack.id);
    router.push("/intake");
  };

  const confirmSwitch = () => {
    if (!confirming) return;
    setIndustry(confirming.id);
    router.push("/intake");
  };

  return (
    <div className="container-x py-12">
      <div className="max-w-2xl">
        <Eyebrow>Step 1 of 3</Eyebrow>
        <h1 className="mt-2 font-display text-4xl font-bold tracking-tight text-ink sm:text-5xl">
          Which of these is closest to your business?
        </h1>
        <p className="mt-3 text-muted">
          Your answer changes the questions we ask, the models we run, the relationships between them,
          and the words on screen. Pick the nearest fit; you can change it later.
        </p>
      </div>

      {error && <div className="mt-8"><ErrorPanel error={error} /></div>}
      {!industries && !error && (
        <div className="mt-8">
          <LoadingPanel title="Loading industries" detail="Reading the packs from the engine registry." />
        </div>
      )}

      {industries && (
        <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {industries.map((pack) => {
            const active = industry === pack.id;
            return (
              <button
                key={pack.id}
                onClick={() => choose(pack)}
                className={`group flex h-full flex-col rounded-2xl border bg-surface p-6 text-left shadow-card transition-all hover:-translate-y-0.5 hover:border-brand hover:shadow-lift ${
                  active ? "border-brand ring-1 ring-brand" : "border-rule"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <h2 className="font-display text-lg font-bold text-ink">{pack.name}</h2>
                  {active && (
                    <span className="shrink-0 rounded-full bg-brand/10 px-2 py-0.5 font-mono text-[0.6rem] uppercase tracking-wide text-brand">
                      selected
                    </span>
                  )}
                </div>

                {/* The industry's own risks, in its own words. */}
                <ul className="mt-4 flex-1 space-y-1.5">
                  {pack.engines.map((e) => (
                    <li key={e.engine} className="flex items-start gap-2 text-sm text-ink/80">
                      <span aria-hidden className="mt-[0.45rem] h-1 w-1 shrink-0 rounded-full bg-brand" />
                      {e.label}
                    </li>
                  ))}
                </ul>

                <div className="mt-5 flex items-center justify-between border-t border-rule pt-3 font-mono text-[0.66rem] text-muted">
                  <span className="tnum">
                    {pack.engines.length} models · {pack.questions.length} questions
                  </span>
                  <span className="text-brand opacity-0 transition-opacity group-hover:opacity-100">
                    Start →
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {confirming && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4" role="dialog" aria-modal="true">
          <div className="w-full max-w-md rounded-2xl border border-rule bg-surface p-6 shadow-lift">
            <h2 className="font-display text-xl font-bold text-ink">Switch to {confirming.name}?</h2>
            <p className="mt-2 text-sm text-muted">
              Your current answers were for a different industry and ask about different things, so
              switching clears them. Nothing else is lost.
            </p>
            <div className="mt-5 flex gap-3">
              <button
                onClick={confirmSwitch}
                className="rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-deep"
              >
                Switch and clear answers
              </button>
              <button
                onClick={() => setConfirming(null)}
                className="rounded-lg border border-rule px-4 py-2.5 text-sm font-medium text-ink hover:border-brand hover:text-brand"
              >
                Keep what I have
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
