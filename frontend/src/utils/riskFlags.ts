export type RiskFlag = { level: 'warn' | 'danger'; label: string };

type StockLike = {
  current_price?: number | null;
  stop_loss_point?: number | null;
  holding_days?: number | null;
  max_holding_days?: number | null;
  market_value?: number | null;
};

type RiskParams = {
  maxHoldingDays?: number | null;
  checkHoldingPeriod?: boolean;
  maxPositionRatio?: number | null;
};

/**
 * Rule-based "should I sell?" hints shared by the workbench and the portfolio holdings table.
 * Pure function so both call sites stay in sync.
 */
export function riskFlags(
  stock: StockLike,
  params: RiskParams,
  totalMarketValue: number,
  labels: { brokenStop: string; nearStop: string; overHolding: string; holdingDue: string; overWeight: string },
): RiskFlag[] {
  const flags: RiskFlag[] = [];
  const price = stock.current_price;
  const stop = stock.stop_loss_point;

  if (price != null && stop != null) {
    if (price <= stop) flags.push({ level: 'danger', label: labels.brokenStop });
    else if ((price - stop) / price <= 0.03) flags.push({ level: 'warn', label: labels.nearStop });
  }

  const maxDays = stock.max_holding_days ?? params.maxHoldingDays;
  const checkPeriod = params.checkHoldingPeriod !== false;
  if (checkPeriod && maxDays && stock.holding_days != null) {
    const remaining = maxDays - stock.holding_days;
    if (remaining <= 0) flags.push({ level: 'danger', label: labels.overHolding });
    else if (remaining <= 5) flags.push({ level: 'warn', label: labels.holdingDue });
  }

  const ratio = params.maxPositionRatio;
  if (ratio && totalMarketValue > 0 && (stock.market_value ?? 0) / totalMarketValue > ratio) {
    flags.push({ level: 'warn', label: labels.overWeight });
  }

  return flags;
}
