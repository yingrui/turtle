/**
 * 后端返回的是不带时区的 UTC 时间戳（Postgres 的 naive datetime 序列化成 "2026-11-04T03:34:22"）。
 * 直接切片会显示成 UTC 时钟，比本地时间早 8 小时。这里统一补上 Z 再按本地时区格式化。
 */
export function localDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const iso = value.endsWith('Z') || value.includes('+') ? value : `${value}Z`;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? value.slice(0, 19) : date.toLocaleString();
}

/** 只要日期时用这个；同样按本地时区换算。 */
export function localDate(value: string | null | undefined): string {
  if (!value) return '—';
  const iso = value.endsWith('Z') || value.includes('+') ? value : `${value}Z`;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? value.slice(0, 10) : date.toLocaleDateString();
}
