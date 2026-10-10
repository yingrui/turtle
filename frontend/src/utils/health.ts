/**
 * Compact `HH:MM:SS` for the header health chip. Locale-independent on purpose:
 * a two-digit clock reads the same in every language and stays narrow.
 */
export function formatCheckedAt(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}
