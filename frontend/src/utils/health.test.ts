import { describe, expect, it } from 'vitest';
import { formatCheckedAt } from './health';

describe('formatCheckedAt', () => {
  it('zero-pads hours, minutes and seconds', () => {
    expect(formatCheckedAt(new Date(2026, 9, 10, 3, 4, 5))).toBe('03:04:05');
  });

  it('keeps two-digit values as-is', () => {
    expect(formatCheckedAt(new Date(2026, 9, 10, 23, 59, 58))).toBe('23:59:58');
  });
});
