import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { DataTable, type Column } from './DataTable';

type Row = { code: string; name: string | null; pct: number | null };

const columns: Column<Row>[] = [
  { key: 'code', label: 'Code', sortable: true, sortValue: (r) => r.code, render: (r) => r.code },
  {
    key: 'name',
    label: 'Name',
    sortable: true,
    sortValue: (r) => r.name,
    render: (r) => r.name ?? '—',
  },
  {
    key: 'pct',
    label: 'Chg',
    align: 'right',
    sortable: true,
    defaultOrder: 'desc',
    sortValue: (r) => r.pct,
    render: (r) => (r.pct == null ? '—' : r.pct.toFixed(2)),
  },
];

const rows: Row[] = [
  { code: '600519.SH', name: 'A', pct: 1.5 },
  { code: '000001.SZ', name: 'B', pct: -2 },
  { code: '300750.SZ', name: null, pct: null },
];

const bodyOrder = (html: string) => [...html.matchAll(/<td[^>]*>(?:<[^>]+>)*([^<]*)/g)].map((m) => m[1]);

describe('DataTable', () => {
  it('renders rows unsorted when no default sort column is given', () => {
    const html = renderToStaticMarkup(<DataTable columns={columns} rows={rows} rowKey={(r) => r.code} />);
    expect(html).toContain('600519.SH');
    expect(html).toContain('—'); // null cells fall back to a placeholder
    expect(html).toContain('class="num"'); // right-aligned column
  });

  it('sorts by the default column and order', () => {
    const html = renderToStaticMarkup(
      <DataTable columns={columns} rows={rows} rowKey={(r) => r.code} defaultSortCol="pct" defaultSortOrder="desc" />,
    );
    const firstCell = bodyOrder(html)[0];
    expect(firstCell).toBe('600519.SH');
  });

  it('keeps nulls last regardless of direction', () => {
    const html = renderToStaticMarkup(
      <DataTable columns={columns} rows={rows} rowKey={(r) => r.code} defaultSortCol="pct" defaultSortOrder="asc" />,
    );
    const codes = bodyOrder(html).filter((c) => c.endsWith('.SH') || c.endsWith('.SZ'));
    expect(codes[0]).toBe('000001.SZ');
    expect(codes[2]).toBe('300750.SZ'); // null pct sorts last
  });

  it('respects controlled sorting (server-side feeds pre-sorted rows)', () => {
    const html = renderToStaticMarkup(
      <DataTable
        columns={columns}
        rows={[rows[2], rows[1], rows[0]]}
        rowKey={(r) => r.code}
        sortCol="code"
        sortOrder="asc"
        onSortChange={() => {}}
      />,
    );
    const codes = bodyOrder(html).filter((c) => c.endsWith('.SH') || c.endsWith('.SZ'));
    expect(codes[0]).toBe('300750.SZ'); // untouched: the parent owns the order
  });

  it('renders empty and loading slots', () => {
    const empty = renderToStaticMarkup(
      <DataTable columns={columns} rows={[]} rowKey={(r) => r.code} empty="nothing here" />,
    );
    expect(empty).toContain('nothing here');
    expect(empty).not.toContain('<table');

    const loading = renderToStaticMarkup(
      <DataTable columns={columns} rows={rows} rowKey={(r) => r.code} loading loadingLabel="loading…" />,
    );
    expect(loading).toContain('loading…');
    expect(loading).not.toContain('<table');
  });

  it('renders selection checkboxes when selectable', () => {
    const html = renderToStaticMarkup(
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.code}
        selectable
        selected={new Set(['000001.SZ'])}
      />,
    );
    expect(html.match(/type="checkbox"/g)).toHaveLength(4); // header + 3 rows
    expect(html).toContain('data-table-select');
  });
});
