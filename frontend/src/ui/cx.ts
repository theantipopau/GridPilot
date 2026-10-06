/** Join class names, keeping only non-empty strings. Accepts `unknown` so
 *  idiomatic `cond && "class"` guards compile whatever `cond` is (ReactNode,
 *  number, object) - the whole app builds class strings this way. */
export function cx(...parts: unknown[]): string {
  return parts.filter((p): p is string => typeof p === "string" && p.length > 0).join(" ");
}
