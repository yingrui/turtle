export type SortOrder = 'asc' | 'desc';

export function compareSortValues(a: unknown, b: unknown, order: SortOrder): number {
  const mul = order === 'asc' ? 1 : -1;
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  if (typeof a === 'number' && typeof b === 'number') {
    if (Number.isNaN(a) && Number.isNaN(b)) return 0;
    if (Number.isNaN(a)) return 1;
    if (Number.isNaN(b)) return -1;
    return (a - b) * mul;
  }
  return String(a).localeCompare(String(b), 'zh-CN') * mul;
}

export function sortIndicator(activeCol: string, col: string, order: SortOrder): string {
  if (activeCol !== col) return '';
  return order === 'asc' ? ' ↑' : ' ↓';
}

export function toggleSortColumn(
  currentCol: string,
  currentOrder: SortOrder,
  col: string,
  defaultDesc = false,
): { col: string; order: SortOrder } {
  if (currentCol === col) {
    return { col, order: currentOrder === 'asc' ? 'desc' : 'asc' };
  }
  return { col, order: defaultDesc ? 'desc' : 'asc' };
}
