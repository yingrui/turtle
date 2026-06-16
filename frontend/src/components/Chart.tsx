import ReactECharts from 'echarts-for-react';

type Series = { name: string; data: (number | null)[] };

type ChartData = {
  dates: string[];
  series: Series[];
};

export type OhlcvData = {
  dates: string[];
  open: number[];
  high: number[];
  low: number[];
  close: number[];
  vol: number[];
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

export function CandlestickChart({ data, title }: { data: OhlcvData; title?: string }) {
  const candleData = data.dates.map((_, i) => [
    data.open[i],
    data.close[i],
    data.low[i],
    data.high[i],
  ]);

  const option = {
    title: title ? { text: title, left: 'center' } : undefined,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      { left: 50, right: 20, top: title ? 50 : 20, height: '58%' },
      { left: 50, right: 20, top: '72%', height: '18%' },
    ],
    xAxis: [
      { type: 'category', data: data.dates, boundaryGap: true, axisLine: { onZero: false } },
      { type: 'category', gridIndex: 1, data: data.dates, boundaryGap: true, axisLabel: { show: false } },
    ],
    yAxis: [
      { scale: true, splitArea: { show: true } },
      { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 70, end: 100 },
      { show: true, xAxisIndex: [0, 1], type: 'slider', bottom: 10, start: 70, end: 100 },
    ],
    series: [
      {
        name: 'K',
        type: 'candlestick',
        data: candleData,
        itemStyle: {
          color: '#ef4444',
          color0: '#16a34a',
          borderColor: '#ef4444',
          borderColor0: '#16a34a',
        },
      },
      {
        name: 'Volume',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: data.vol,
        itemStyle: {
          color: (params: { dataIndex: number }) =>
            data.close[params.dataIndex] >= data.open[params.dataIndex] ? '#ef4444' : '#16a34a',
        },
      },
    ],
  };
  return <ReactECharts option={option} style={{ height: 480 }} />;
}
