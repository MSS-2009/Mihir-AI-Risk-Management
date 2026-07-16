import { Badge } from "./ui";

/** The AI narrative, clearly attributed as interpretation of the model output. */
export function InterpretationPanel({
  text,
  aiEnabled,
}: {
  text: string;
  aiEnabled?: boolean;
}) {
  const fellBack = text.includes("Live AI unavailable") || aiEnabled === false;
  return (
    <div className="rounded-xl border border-bordeaux/15 bg-bordeaux/[0.03] p-5">
      <div className="flex items-center justify-between">
        <div className="eyebrow text-bordeaux/80">Interpretation</div>
        <Badge tone={fellBack ? "ochre" : "bordeaux"}>
          {fellBack ? "Deterministic summary" : "AI reading of the model"}
        </Badge>
      </div>
      <p className="mt-3 whitespace-pre-line text-[0.95rem] leading-relaxed text-ink/90">{text}</p>
      <p className="mt-3 border-t border-bordeaux/10 pt-3 text-[0.72rem] text-muted">
        Interprets the simulation output only. It introduces no figures beyond those the models computed.
      </p>
    </div>
  );
}
