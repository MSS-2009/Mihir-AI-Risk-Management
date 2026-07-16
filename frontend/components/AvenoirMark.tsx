/** The Avenoir "A" mark: a peaked A with a crimson shield/dot, echoing the deck logo. */
export function AvenoirMark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 40 40" fill="none" aria-hidden xmlns="http://www.w3.org/2000/svg">
      {/* outer peak (the A) */}
      <path d="M20 3 L37 36 L29 36 L20 17 L11 36 L3 36 Z" fill="#0B0A0A" />
      {/* crimson shield/flame inside */}
      <path d="M20 13 C24 18 24 24 20 28 C16 24 16 18 20 13 Z" fill="#8F0F24" />
      {/* base dot */}
      <circle cx="20" cy="24.5" r="2.4" fill="#C11530" />
    </svg>
  );
}
