import { ReactNode } from "react";
import { Button, Card } from "./ui";

/** Loading, shows what's happening, not a bare spinner. */
export function LoadingPanel({
  title = "Running simulations",
  detail = "Drawing 10,000+ scenarios across each risk domain and correlating the tails.",
}: {
  title?: string;
  detail?: string;
}) {
  return (
    <Card className="p-8">
      <div className="flex items-center gap-3">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-bordeaux/50" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-bordeaux" />
        </span>
        <span className="font-medium text-ink">{title}…</span>
      </div>
      <p className="mt-3 max-w-md text-sm text-muted">{detail}</p>
      <div className="mt-5 space-y-2">
        {["Sampling domain distributions", "Applying the correlation structure", "Interpreting for the CFO"].map(
          (s, i) => (
            <div key={s} className="flex items-center gap-2 text-sm text-muted">
              <span
                className="h-1 w-8 overflow-hidden rounded-full bg-mist"
                style={{ animationDelay: `${i * 150}ms` }}
              >
                <span className="block h-full w-full animate-fade-up bg-bordeaux/40" />
              </span>
              {s}
            </div>
          )
        )}
      </div>
    </Card>
  );
}

/** Error, say what happened and how to fix it. Never vague. */
export function ErrorPanel({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <Card className="border-ochre/30 p-6">
      <div className="font-mono text-[0.7rem] uppercase tracking-wide text-ochre">Something interrupted the run</div>
      <p className="mt-2 text-sm text-ink">{error}</p>
      {onRetry && (
        <div className="mt-4">
          <Button variant="outline" onClick={onRetry}>
            Try again
          </Button>
        </div>
      )}
    </Card>
  );
}

/** Empty, an invitation to act, with a one-click example. */
export function EmptyPanel({
  title,
  detail,
  action,
}: {
  title: string;
  detail: string;
  action?: ReactNode;
}) {
  return (
    <Card className="border-dashed p-10 text-center">
      <h3 className="font-display text-xl font-semibold text-ink">{title}</h3>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted">{detail}</p>
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </Card>
  );
}
