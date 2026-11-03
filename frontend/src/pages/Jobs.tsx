import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../utils/api';
import { DataTable, type Column } from '../components/DataTable';

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
      render: (row) => (row.started_at ? row.started_at.slice(0, 19).replace('T', ' ') : '—'),
    },
    {
      key: 'finished',
      label: t('tasks.colFinished'),
      render: (row) => (row.finished_at ? row.finished_at.slice(0, 19).replace('T', ' ') : '—'),
    },
    { key: 'detail', label: t('tasks.colDetail'), render: (row) => row.detail ?? '—' },
    { key: 'error', label: t('tasks.colError'), render: (row) => row.error ?? '—' },
  ];

  return (
    <div className="datasets-page">
      <header className="datasets-header">
        <h1>{t('tasks.title')}</h1>
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
