// Case-insensitive substring match across a candidate's searchable
// fields - shared by every review-queue search box (SearchBox.tsx) so
// "does this candidate match" is defined once, not once per queue.
export function matchesQuery(query: string, fields: (string | null | undefined)[]): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return fields.some((f) => f?.toLowerCase().includes(q));
}
