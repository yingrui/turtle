import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { apiFetch } from '../utils/api';
import { useJobPoll } from '../hooks/useJobPoll';
import { compareSortValues, sortIndicator, toggleSortColumn, type SortOrder } from '../utils/tableSort';

type DataStatus = {
  as_of_date: string | null;
  tables: { name: string; latest_trade_date: string | null }[];
};

type PickPreset = {
  id: string;
  name: string;
  name_en: string;
  params: Record<string, unknown>;
};

type PickRow = {
  ts_code: string;
  name?: string;
  industry?: string;
  close?: number;
  pe_ttm?: number;
  pb?: number;
  circ_mv?: number;
  turnover_rate?: number;
  pct_chg?: number;
};

type ScreenRow = {
  ts_code: string;
  name?: string;
  industry?: string;
  trend?: string;
  trend_reason?: string;
  adf?: number;
  gradient?: number;
  bar_count?: number;
};

type ResultRow = PickRow | ScreenRow;

function isPickRow(row: ResultRow): row is PickRow {
  return 'pe_ttm' in row || 'pb' in row || 'circ_mv' in row;
}

function getSortValue(row: ResultRow, col: string): string | number | null | undefined {
  if (col === 'ts_code') return row.ts_code;
  if (col === 'name') return isPickRow(row) ? row.name : (row as ScreenRow).name;
  if (col === 'industry') return row.industry;
  if (isPickRow(row)) {
    if (col === 'pe_ttm') return row.pe_ttm;
    if (col === 'pb') return row.pb;
    if (col === 'circ_mv') return row.circ_mv;
    if (col === 'pct_chg') return row.pct_chg;
  } else {
    const tech = row as ScreenRow;
    if (col === 'trend') return tech.trend;
    if (col === 'trend_reason') return tech.trend_reason;
    if (col === 'adf') return tech.adf;
    if (col === 'gradient') return tech.gradient;
    if (col === 'bar_count') return tech.bar_count;
  }
  return null;
}

function SortableTh({
  col,
  label,
  sortCol,
  sortOrder,
  onSort,
  defaultDesc = false,
}: {
  col: string;
  label: string;
  sortCol: string;
  sortOrder: SortOrder;
  onSort: (col: string, defaultDesc?: boolean) => void;
  defaultDesc?: boolean;
}) {
  return (
    <th className="sortable" onClick={() => onSort(col, defaultDesc)}>
      {label}
      {sortIndicator(sortCol, col, sortOrder)}
    </th>
  );
}

export function Screening() {
  const { t, i18n } = useTranslation();
  const [tab, setTab] = useState<'fundamental' | 'technical'>('fundamental');
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null);
  const [presets, setPresets] = useState<PickPreset[]>([]);
  const [portfolios, setPortfolios] = useState<string[]>([]);

  const [peMax, setPeMax] = useState('');
  const [pbMax, setPbMax] = useState('');
  const [circMvMax, setCircMvMax] = useState('');
  const [industry, setIndustry] = useState('');
  const [excludeSt, setExcludeSt] = useState(true);
  const [pickLoading, setPickLoading] = useState(false);
  const [pickRows, setPickRows] = useState<PickRow[]>([]);
  const [pickTotal, setPickTotal] = useState(0);
  const [pickAsOf, setPickAsOf] = useState<string | null>(null);

  const [asOfDate, setAsOfDate] = useState(new Date().toISOString().slice(0, 10));
  const [trendFilter, setTrendFilter] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);
  const [techRows, setTechRows] = useState<ScreenRow[]>([]);
  const job = useJobPoll(jobId);

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkPortfolio, setBulkPortfolio] = useState('');
  const [backtestOpen, setBacktestOpen] = useState(false);
  const [btPortfolio, setBtPortfolio] = useState('');
  const [btStart, setBtStart] = useState('2024-01-01');
  const [btEnd, setBtEnd] = useState(new Date().toISOString().slice(0, 10));
  const [simJobId, setSimJobId] = useState<string | null>(null);
  const simJob = useJobPoll(simJobId);

  const [sortCol, setSortCol] = useState('circ_mv');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');

  const activeRows: ResultRow[] = tab === 'fundamental' ? pickRows : techRows;
  const allCodes = useMemo(() => activeRows.map((r) => r.ts_code), [activeRows]);

  const sortedRows = useMemo(() => {
    const rows = [...activeRows];
    rows.sort((a, b) => compareSortValues(getSortValue(a, sortCol), getSortValue(b, sortCol), sortOrder));
    return rows;
  }, [activeRows, sortCol, sortOrder]);

  useEffect(() => {
    if (tab === 'fundamental') {
      setSortCol('circ_mv');
      setSortOrder('asc');
    } else {
      setSortCol('gradient');
      setSortOrder('desc');
    }
  }, [tab]);

  function onSortColumn(col: string, defaultDesc = false) {
    const next = toggleSortColumn(sortCol, sortOrder, col, defaultDesc);
    setSortCol(next.col);
    setSortOrder(next.order);
  }

  useEffect(() => {
    apiFetch<DataStatus>('/api/data/status').then((d) => {
      setDataStatus(d);
      if (d.as_of_date) setAsOfDate(d.as_of_date);
    }).catch(() => {});
    apiFetch<{ presets: PickPreset[] }>('/api/stock-pick/presets').then((d) => setPresets(d.presets)).catch(() => {});
    apiFetch<{ portfolios: string[] }>('/api/portfolios')
      .then((d) => {
        setPortfolios(d.portfolios);
        if (d.portfolios[0]) {
          setBulkPortfolio(d.portfolios[0]);
          setBtPortfolio(d.portfolios[0]);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (job?.status !== 'completed' || !job.result) return;
    try {
      const parsed = JSON.parse(job.result) as { stocks: ScreenRow[] };
      setTechRows(parsed.stocks ?? []);
      setSelected(new Set());
    } catch {
      setTechRows([]);
    }
  }, [job?.status, job?.result]);

  const dailyBasicDate = dataStatus?.tables.find((t) => t.name === 'daily_basic')?.latest_trade_date;

  async function runPick(override?: Record<string, unknown>) {
    setPickLoading(true);
    try {
      const body: Record<string, unknown> = {
        exclude_st: excludeSt,
        exclude_limit: true,
        limit: 200,
        sort: 'circ_mv',
        order: 'asc',
        ...override,
      };
      if (peMax) body.pe_ttm_max = Number(peMax);
      if (pbMax) body.pb_max = Number(pbMax);
      if (circMvMax) body.circ_mv_max = Number(circMvMax);
      if (industry) body.industry = industry;

      const res = await apiFetch<{ as_of_date: string | null; total: number; items: PickRow[] }>(
        '/api/stock-pick',
        { method: 'POST', body: JSON.stringify(body) },
      );
      setPickRows(res.items);
      setPickTotal(res.total);
      setPickAsOf(res.as_of_date);
      setSelected(new Set());
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('screening.pickFailed'));
    } finally {
      setPickLoading(false);
    }
  }

  async function onScreen() {
    try {
      const res = await apiFetch<{ id: string }>('/api/jobs', {
        method: 'POST',
        body: JSON.stringify({
          type: 'portfolio_screen',
          as_of_date: asOfDate,
          ignore_st: true,
          trend_filter: trendFilter || undefined,
        }),
      });
      setJobId(res.id);
      setTechRows([]);
      setSelected(new Set());
      toast.success(t('screening.techStarted'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('screening.techFailed'));
    }
  }

  async function addToWatchlist(tsCodes: string[], portfolio: string) {
    if (!portfolio || tsCodes.length === 0) return;
    try {
      await apiFetch(`/api/portfolios/${encodeURIComponent(portfolio)}/watchlist/bulk`, {
        method: 'POST',
        body: JSON.stringify({ ts_codes: tsCodes }),
      });
      toast.success(t('screening.addedWatchlist', { count: tsCodes.length, portfolio }));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed');
    }
  }

  async function runBacktest() {
    const codes = selected.size > 0 ? [...selected] : allCodes;
    if (!btPortfolio || codes.length === 0) return;
    try {
      const res = await apiFetch<{ id: string }>('/api/jobs', {
        method: 'POST',
        body: JSON.stringify({
          type: 'simulation',
          portfolio: btPortfolio,
          start_date: btStart,
          end_date: btEnd,
          ts_codes: codes,
        }),
      });
      setSimJobId(res.id);
      toast.success(t('screening.backtestStarted', { count: codes.length }));
      setBacktestOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed');
    }
  }

  function toggleAll(checked: boolean) {
    setSelected(checked ? new Set(allCodes) : new Set());
  }

  function toggleOne(code: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  }

  function applyPreset(preset: PickPreset) {
    const p = preset.params;
    setPeMax(p.pe_ttm_max != null ? String(p.pe_ttm_max) : '');
    setPbMax(p.pb_max != null ? String(p.pb_max) : '');
    setCircMvMax(p.circ_mv_max != null ? String(p.circ_mv_max) : '');
    runPick(p);
  }

  const presetLabel = (p: PickPreset) => (i18n.language.startsWith('zh') ? p.name : p.name_en);

  return (
    <div className="page-card">
      <h1 className="page-title">{t('nav.screening')}</h1>
      <p style={{ color: 'var(--color-text-muted)', marginBottom: 'var(--space-3)' }}>
        {t('screening.subtitle')}
      </p>

      {dataStatus && (
        <div
          style={{
            padding: 'var(--space-3)',
            marginBottom: 'var(--space-4)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
            fontSize: 'var(--text-sm)',
          }}
        >
          {t('data.status.asOf')}: <strong>{dataStatus.as_of_date ?? '—'}</strong>
          {dailyBasicDate ? (
            <span> · daily_basic: {dailyBasicDate}</span>
          ) : (
            <span style={{ color: 'var(--color-danger)' }}> · {t('screening.noDailyBasic')}</span>
          )}
          {' · '}
          <Link to="/data">{t('data.status.viewDetails')}</Link>
        </div>
      )}

      <div style={{ display: 'flex', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
        <button
          type="button"
          className={`btn${tab === 'fundamental' ? ' btn-primary' : ' btn-secondary'}`}
          onClick={() => setTab('fundamental')}
        >
          {t('screening.tabFundamental')}
        </button>
        <button
          type="button"
          className={`btn${tab === 'technical' ? ' btn-primary' : ' btn-secondary'}`}
          onClick={() => setTab('technical')}
        >
          {t('screening.tabTechnical')}
        </button>
      </div>

      {tab === 'fundamental' && (
        <>
          <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div className="form-row" style={{ maxWidth: 120 }}>
              <label>{t('screening.peMax')}</label>
              <input type="number" value={peMax} onChange={(e) => setPeMax(e.target.value)} placeholder="20" />
            </div>
            <div className="form-row" style={{ maxWidth: 120 }}>
              <label>{t('screening.pbMax')}</label>
              <input type="number" value={pbMax} onChange={(e) => setPbMax(e.target.value)} placeholder="3" />
            </div>
            <div className="form-row" style={{ maxWidth: 160 }}>
              <label>{t('screening.circMvMax')}</label>
              <input type="number" value={circMvMax} onChange={(e) => setCircMvMax(e.target.value)} placeholder="500000" />
            </div>
            <div className="form-row" style={{ maxWidth: 160 }}>
              <label>{t('screening.industry')}</label>
              <input type="text" value={industry} onChange={(e) => setIndustry(e.target.value)} />
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <input type="checkbox" checked={excludeSt} onChange={(e) => setExcludeSt(e.target.checked)} />
              {t('screening.excludeSt')}
            </label>
            <button type="button" className="btn btn-primary" disabled={pickLoading} onClick={() => runPick()}>
              {pickLoading ? t('screening.running') : t('screening.runPick')}
            </button>
          </div>
          {presets.length > 0 && (
            <div style={{ marginTop: 'var(--space-3)', display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
              <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--text-sm)' }}>{t('screening.presets')}:</span>
              {presets.map((p) => (
                <button key={p.id} type="button" className="btn btn-sm btn-secondary" onClick={() => applyPreset(p)}>
                  {presetLabel(p)}
                </button>
              ))}
            </div>
          )}
          {pickAsOf && (
            <p style={{ marginTop: 'var(--space-3)', fontSize: 'var(--text-sm)' }}>
              {t('screening.pickResult', { date: pickAsOf, shown: pickRows.length, total: pickTotal })}
            </p>
          )}
        </>
      )}

      {tab === 'technical' && (
        <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div className="form-row" style={{ maxWidth: 200 }}>
            <label>{t('screening.asOf')}</label>
            <input type="date" value={asOfDate} onChange={(e) => setAsOfDate(e.target.value)} />
          </div>
          <div className="form-row" style={{ maxWidth: 200 }}>
            <label>{t('screening.trend')}</label>
            <select value={trendFilter} onChange={(e) => setTrendFilter(e.target.value)}>
              <option value="">{t('screening.trendAll')}</option>
              <option value="up">{t('screening.trendUp')}</option>
              <option value="down">{t('screening.trendDown')}</option>
            </select>
          </div>
          <button type="button" className="btn btn-primary" onClick={onScreen}>
            {t('screening.runTech')}
          </button>
          {job && (
            <span>
              {t('screening.jobStatus')}: <strong>{job.status}</strong>
            </span>
          )}
        </div>
      )}

      {job?.error && <p className="error-banner">{job.error}</p>}

      {simJobId && simJob && (
        <div
          style={{
            marginTop: 'var(--space-4)',
            padding: 'var(--space-3)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
            fontSize: 'var(--text-sm)',
          }}
        >
          {t('screening.backtestJob')}: <strong>{simJob.status}</strong>
          {simJob.status === 'completed' && (
            <>
              {' · '}
              <Link to={`/simulation/results?job_id=${encodeURIComponent(simJobId)}`}>
                {t('simulation.viewResults')} →
              </Link>
            </>
          )}
          {simJob.error && <p className="error-banner" style={{ marginTop: 'var(--space-2)' }}>{simJob.error}</p>}
        </div>
      )}

      {activeRows.length > 0 && (
        <div style={{ marginTop: 'var(--space-4)' }}>
          <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap', marginBottom: 'var(--space-3)' }}>
            {portfolios.length > 0 && (
              <>
                <select value={bulkPortfolio} onChange={(e) => setBulkPortfolio(e.target.value)}>
                  {portfolios.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => addToWatchlist(selected.size ? [...selected] : allCodes, bulkPortfolio)}
                >
                  {selected.size > 0
                    ? t('screening.bulkWatchlist', { count: selected.size })
                    : t('screening.bulkWatchlistAll', { count: allCodes.length })}
                </button>
              </>
            )}
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => setBacktestOpen(true)}>
              {t('screening.sendBacktest')}
            </button>
          </div>

          <table className="data-table">
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    checked={selected.size === allCodes.length && allCodes.length > 0}
                    onChange={(e) => toggleAll(e.target.checked)}
                  />
                </th>
                <SortableTh col="ts_code" label={t('quote.col.ts_code')} sortCol={sortCol} sortOrder={sortOrder} onSort={onSortColumn} />
                <SortableTh col="name" label={t('quote.col.name')} sortCol={sortCol} sortOrder={sortOrder} onSort={onSortColumn} />
                <SortableTh col="industry" label={t('quote.col.industry')} sortCol={sortCol} sortOrder={sortOrder} onSort={onSortColumn} />
                {tab === 'fundamental' ? (
                  <>
                    <SortableTh col="pe_ttm" label="PE" sortCol={sortCol} sortOrder={sortOrder} onSort={onSortColumn} defaultDesc />
                    <SortableTh col="pb" label="PB" sortCol={sortCol} sortOrder={sortOrder} onSort={onSortColumn} defaultDesc />
                    <SortableTh col="circ_mv" label={t('screening.circMv')} sortCol={sortCol} sortOrder={sortOrder} onSort={onSortColumn} defaultDesc />
                    <SortableTh col="pct_chg" label={t('quote.col.pct_chg')} sortCol={sortCol} sortOrder={sortOrder} onSort={onSortColumn} defaultDesc />
                  </>
                ) : (
                  <>
                    <SortableTh col="trend" label={t('screening.trend')} sortCol={sortCol} sortOrder={sortOrder} onSort={onSortColumn} />
                    <SortableTh col="trend_reason" label={t('screening.trendReasonCol')} sortCol={sortCol} sortOrder={sortOrder} onSort={onSortColumn} />
                    <SortableTh col="adf" label="ADF" sortCol={sortCol} sortOrder={sortOrder} onSort={onSortColumn} defaultDesc />
                    <SortableTh col="gradient" label="Gradient" sortCol={sortCol} sortOrder={sortOrder} onSort={onSortColumn} defaultDesc />
                  </>
                )}
                <th>{t('quote.col.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {sortedRows.slice(0, 200).map((row) => (
                <tr key={row.ts_code}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selected.has(row.ts_code)}
                      onChange={() => toggleOne(row.ts_code)}
                    />
                  </td>
                  <td>
                    <Link to={`/stocks/${encodeURIComponent(row.ts_code)}`}>{row.ts_code}</Link>
                  </td>
                  <td>{isPickRow(row) ? row.name ?? '' : (row as ScreenRow).name ?? ''}</td>
                  <td>{row.industry ?? ''}</td>
                  {tab === 'fundamental' && isPickRow(row) ? (
                    <>
                      <td>{row.pe_ttm != null ? row.pe_ttm.toFixed(2) : ''}</td>
                      <td>{row.pb != null ? row.pb.toFixed(2) : ''}</td>
                      <td>{row.circ_mv != null ? Math.round(row.circ_mv).toLocaleString() : ''}</td>
                      <td>{row.pct_chg != null ? row.pct_chg.toFixed(2) : ''}</td>
                    </>
                  ) : !isPickRow(row) ? (
                    <>
                      <td>{row.trend ?? ''}</td>
                      <td className="screening-trend-reason" title={row.trend_reason}>
                        {row.trend_reason ? t(`screening.trendReason.${row.trend_reason}`, { count: row.bar_count ?? 0 }) : '—'}
                      </td>
                      <td>{row.adf != null ? Number(row.adf).toFixed(4) : ''}</td>
                      <td>{row.gradient != null ? Number(row.gradient).toFixed(4) : ''}</td>
                    </>
                  ) : null}
                  <td>
                    {portfolios[0] && (
                      <button
                        type="button"
                        className="btn btn-sm"
                        onClick={() => addToWatchlist([row.ts_code], bulkPortfolio || portfolios[0])}
                      >
                        {t('quote.watchlist')}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {backtestOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
          }}
          onClick={() => setBacktestOpen(false)}
        >
          <div
            className="page-card"
            style={{ maxWidth: 420, width: '90%' }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 style={{ fontSize: 'var(--text-lg)', marginBottom: 'var(--space-3)' }}>{t('screening.backtestTitle')}</h2>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)' }}>
              {t('screening.backtestHint', { count: selected.size || allCodes.length })}
            </p>
            <div className="form-row">
              <label>{t('watchlist.portfolio')}</label>
              <select value={btPortfolio} onChange={(e) => setBtPortfolio(e.target.value)}>
                {portfolios.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
            <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
              <div className="form-row">
                <label>{t('screening.startDate')}</label>
                <input type="date" value={btStart} onChange={(e) => setBtStart(e.target.value)} />
              </div>
              <div className="form-row">
                <label>{t('screening.endDate')}</label>
                <input type="date" value={btEnd} onChange={(e) => setBtEnd(e.target.value)} />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-4)' }}>
              <button type="button" className="btn btn-primary" onClick={runBacktest}>
                {t('screening.runBacktest')}
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => setBacktestOpen(false)}>
                {t('screening.cancel')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
