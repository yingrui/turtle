import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { apiFetch } from '../utils/api';

type PortfolioContextValue = {
  portfolios: string[];
  portfolio: string;
  setPortfolio: (name: string) => void;
  reload: () => Promise<string[]>;
};

const PortfolioContext = createContext<PortfolioContextValue | null>(null);

const STORAGE_KEY = 'turtle.portfolio';

function storedPortfolio(): string {
  try {
    return window.localStorage.getItem(STORAGE_KEY) ?? '';
  } catch {
    return '';
  }
}

/**
 * One portfolio selector for the whole app. The choice lives in a header control, survives
 * reloads via localStorage, and every page reads it from here instead of keeping its own.
 */
export function PortfolioProvider({ children }: { children: ReactNode }) {
  const [portfolios, setPortfolios] = useState<string[]>([]);
  const [portfolio, setPortfolioState] = useState<string>(storedPortfolio);

  const reload = useCallback(async () => {
    const data = await apiFetch<{ portfolios: string[] }>('/api/portfolios');
    const names = data.portfolios ?? [];
    setPortfolios(names);
    setPortfolioState((current) => {
      const next = current && names.includes(current) ? current : (names[0] ?? '');
      if (next !== current) {
        try {
          window.localStorage.setItem(STORAGE_KEY, next);
        } catch {
          /* ignore private-mode failures */
        }
      }
      return next;
    });
    return names;
  }, []);

  useEffect(() => {
    reload().catch(() => setPortfolios([]));
  }, [reload]);

  const setPortfolio = useCallback((name: string) => {
    setPortfolioState(name);
    try {
      window.localStorage.setItem(STORAGE_KEY, name);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo(
    () => ({ portfolios, portfolio, setPortfolio, reload }),
    [portfolios, portfolio, setPortfolio, reload],
  );
  return <PortfolioContext.Provider value={value}>{children}</PortfolioContext.Provider>;
}

export function usePortfolioContext(): PortfolioContextValue {
  const ctx = useContext(PortfolioContext);
  if (!ctx) throw new Error('usePortfolioContext must be used inside PortfolioProvider');
  return ctx;
}
