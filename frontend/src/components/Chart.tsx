import ReactECharts from 'echarts-for-react';

type Series = { name: string; data: (number | null)[] };

type ChartData = {
  dates: string[];
  series: Series[];
};

export function LineChart({ data, title }: { data: ChartData; title?: string }) {
  const option = {
    title: title ? { text: title, left: 'center' } : undefined,
    tooltip: { trigger: 'axis' },
    legend: { top: 30 },
    grid: { left: 50, right: 20, top: 70, bottom: 40 },
    xAxis: { type: 'category', data: data.dates },
    yAxis: { type: 'value', scale: true },
    series: data.series.map((s) => ({
      name: s.name,
      type: 'line',
      showSymbol: false,
      data: s.data,
    })),
  };
  return <ReactECharts option={option} style={{ height: 400 }} />;
}
