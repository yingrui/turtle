import { describe, expect, it } from 'vitest';
import { config } from '../config';

describe('api config', () => {
  it('uses empty string as default api url for same-origin proxy', () => {
    expect(config.apiUrl).toBe('');
  });
});
