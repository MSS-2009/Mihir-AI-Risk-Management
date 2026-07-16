/**
 * The Avenoir signature: flowing fields of small dots forming wave/swirl bands,
 * lifted from the pitch deck. Deterministic math (no random) so server and client
 * render identically. Purely decorative, so aria-hidden.
 */
type Props = {
  className?: string;
  /** corner the waves flow from */
  corner?: "tl" | "tr" | "bl" | "br";
  color?: string;
  /** number of wavy bands */
  rows?: number;
  /** dots per band */
  cols?: number;
  opacity?: number;
  drift?: boolean;
};

export function DottedWaves({
  className = "",
  corner = "tl",
  color = "#C11530",
  rows = 22,
  cols = 42,
  opacity = 0.55,
  drift = false,
}: Props) {
  const W = 460;
  const H = 460;
  const dots: { x: number; y: number; r: number; o: number }[] = [];

  for (let r = 0; r < rows; r++) {
    const rowT = r / (rows - 1); // 0..1 outward from corner
    for (let c = 0; c < cols; c++) {
      const colT = c / (cols - 1);
      const x = colT * W;
      // layered sine bands, tighter and taller near the corner
      const amp = 26 * (1 - rowT * 0.55);
      const y =
        rowT * H * 0.92 +
        amp * Math.sin(colT * 6.3 + r * 0.55) +
        10 * Math.sin(colT * 13 + r * 0.9);
      // swirl: pull columns inward toward the corner
      const swirl = (1 - colT) * 34 * Math.sin(rowT * 3.14);
      const px = x - swirl;
      // fade with distance from the corner
      const dist = Math.sqrt(px * px + y * y) / Math.sqrt(W * W + H * H);
      const o = Math.max(0, opacity * (1 - dist * 1.15) * (0.5 + colT * 0.5));
      if (o <= 0.02) continue;
      const rad = 1.7 * (1 - rowT * 0.4) * (0.7 + colT * 0.5);
      dots.push({ x: px, y, r: rad, o });
    }
  }

  const transform = {
    tl: "",
    tr: `scale(-1,1) translate(-${W},0)`,
    bl: `scale(1,-1) translate(0,-${H})`,
    br: `scale(-1,-1) translate(-${W},-${H})`,
  }[corner];

  return (
    <svg
      aria-hidden
      viewBox={`0 0 ${W} ${H}`}
      className={`${className} ${drift ? "motion-safe:animate-wave-drift" : ""}`}
      preserveAspectRatio="xMidYMid meet"
      fill={color}
    >
      <g transform={transform}>
        {dots.map((d, i) => (
          <circle key={i} cx={d.x} cy={d.y} r={d.r} opacity={d.o} />
        ))}
      </g>
    </svg>
  );
}
