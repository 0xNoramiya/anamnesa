export type CurrencyKind = "current" | "aging" | "superseded" | "withdrawn";

const LABELS_ID: Record<CurrencyKind, string> = {
  current: "Berlaku",
  aging: "Perlu tinjau",
  superseded: "Sudah diganti",
  withdrawn: "Dicabut",
};

export function CurrencyChip({
  kind,
  year,
}: {
  kind: CurrencyKind;
  year?: number | null;
}) {
  return (
    <span className={`chip chip-${kind}`}>
      <span className="chip-dot" />
      {LABELS_ID[kind]}
      {year ? ` · ${year}` : ""}
    </span>
  );
}
