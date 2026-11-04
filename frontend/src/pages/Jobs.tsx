import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../utils/api';
import { DataTable, type Column } from '../components/DataTable';
import './Jobs.scss';
import { localDateTime } from '../utils/time';

type Task = {
  id: string;
  source: 'job' | 'analysis';
  kind: string;
  title: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  detail: string | null;
  progress: string;
};

/** 统一的运行记录：回测、因子计算、评分模型、导出训练集都在这里，不再分两处看。 */
export function Jobs() {
  const { t } = useTranslation();
  const [tasks, setTasks] = useState<Task[]>([]);

  async function retry(id: string) {
    try {
      await apiFetch(`/api/tasks/${encodeURIComponent(id)}/retry`, { method: 'POST', body: '{}' });
      await load();
    } catch {
      // 失败信息会出现在运行记录里，这里不额外打扰
    }
  }

  const load = useCallback(async () => {
    try {
      const res = await apiFetch<{ tasks: Task[] }>('/api/tasks?limit=200');
      setTasks(res.tasks ?? []);
    } catch {
      setTasks([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const columns: Column<Task>[] = [
    { key: 'title', label: t('tasks.colTitle'), render: (row) => row.title },
    { key: 'status', label: t('tasks.colStatus'), render: (row) => row.status },
    {
      key: 'progress',
      label: t('tasks.colProgress'),
      // 任务自己上报的进度（如 "12/34 · 35%"）；没上报的完成后直接是 100%
      render: (row) => (row.progress ? row.progress : row.status === 'completed' ? '100%' : '—'),
    },
    {
      key: 'started',
      label: t('tasks.colStarted'),
      render: (row) => localDateTime(row.started_at),
    },
    {
      key: 'finished',
      label: t('tasks.colFinished'),
      render: (row) => localDateTime(row.finished_at),
    },
    { key: 'detail', label: t('tasks.colDetail'), render: (row) => row.detail ?? '—' },
    { key: 'error', label: t('tasks.colError'), render: (row) => row.error ?? '—' },
    {
      key: 'actions',
      label: '',
      className: 'tasks-action',
      cellClassName: () => 'tasks-action',
      render: (row) =>
        row.status === 'failed' || row.status === 'completed' ? (
          <button type="button" className="btn-link" onClick={() => retry(row.id)}>
            {t('tasks.retry')}
          </button>
        ) : (
          '—'
        ),
    },
  ];

  return (
    <div className="datasets-page">
      <header className="datasets-header">
        <div className="datasets-head-row">
          <h1>{t('tasks.title')}</h1>
          <button type="button" className="btn btn-secondary" onClick={() => void load()}>
            {t('tasks.refresh')}
          </button>
        </div>
        <p className="datasets-lead">{t('tasks.lead')}</p>
      </header>
      <DataTable<Task>
        columns={columns}
        rows={tasks}
        rowKey={(row) => `${row.source}-${row.id}`}
        empty={t('tasks.empty')}
        pageSize={25}
      />
    </div>
  );
}
