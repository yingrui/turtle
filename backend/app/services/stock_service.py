from app.core.engine.StockRepository import StockRepository
from app.core.engine.StockTradeDataEngine import StockTradeDataEngine
from app.core.engine import stock_universe
from app.core.util import chart_data


class StockService:
    def __init__(self):
        self._engine = StockTradeDataEngine()
        self._repo = StockRepository()

    def list_stocks(self, config: dict) -> list[dict]:
        stocks = [self._repo.find_stock(code) for code in config["follow_stocks"]]
        return [{"ts_code": s.ts_code, "name": s.name} for s in stocks if s]

    def list_universe(self, **kwargs) -> dict:
        return stock_universe.list_universe(**kwargs)

    def get_universe_meta(self) -> dict:
        return stock_universe.get_universe_meta()

    def get_industry_summary(self, **kwargs) -> dict:
        return stock_universe.get_industry_summary(**kwargs)

    def get_stock_snapshot(self, ts_code: str) -> dict | None:
        return stock_universe.get_stock_snapshot(ts_code)

    def search_stocks(self, q: str, limit: int = 20) -> list[dict]:
        return stock_universe.search_stocks(q, limit=limit)

    def get_ohlcv(self, ts_code: str, limit: int = 250) -> dict:
        df = self._engine.get_trade_data_by_code(ts_code)
        if limit > 0:
            df = df.tail(limit)
        if df.empty:
            return {
                "dates": [],
                "open": [],
                "high": [],
                "low": [],
                "close": [],
                "vol": [],
                "pct_chg": [],
            }

        last_adj = float(df.adj_factor.values[-1])
        scale = df.adj_factor / last_adj

        def _qfq(col):
            return [float(v * s) for v, s in zip(col, scale, strict=True)]

        return {
            "dates": [d.strftime("%Y-%m-%d") for d in df.trade_date],
            "open": _qfq(df.open),
            "high": _qfq(df.high),
            "low": _qfq(df.low),
            "close": [float(v) for v in df.qfq],
            "vol": [float(v) for v in df.vol],
            "pct_chg": [float(v) for v in df.pct_chg],
        }

    def get_indicators(self, ts_code: str, chart_type: str) -> dict:
        df = self._engine.get_trade_data_by_code(ts_code)
        if chart_type == "ma":
            return chart_data.moving_average_chart(df.trade_date, df.qfq)
        if chart_type == "atr":
            return chart_data.atr_chart(df.trade_date, df.qfq, df.high - df.low)
        if chart_type == "bolling":
            return chart_data.bolling_chart(df.trade_date, df.qfq)
        if chart_type == "donchian":
            return chart_data.donchian_chart(df.trade_date, df.qfq)
        if chart_type == "distribution":
            return chart_data.distribution_chart(df.trade_date, df.pct_chg)
        raise ValueError(f"Unknown chart type: {chart_type}")

    def forecast(self, ts_code: str, steps: int = 10) -> dict:
        from statsmodels.tsa.arima.model import ARIMA

        df = self._engine.get_trade_data_by_code(ts_code)
        model = ARIMA(df.qfq, order=(5, 1, 0))
        fitted = model.fit()
        forecast = fitted.forecast(steps=steps)
        last_dates = df.trade_date.tail(30)
        hist = chart_data.moving_average_chart(last_dates, df.qfq.tail(30), sma_days_list=[5])
        return {
            "history": hist,
            "forecast": {
                "values": [float(v) for v in forecast],
                "steps": steps,
            },
            "summary": str(fitted.summary()),
        }
