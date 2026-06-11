from datetime import date

from app.core.engine.PortfolioFilter import PortfolioFilter
from app.core.engine.StockTradeDataEngine import StockTradeDataEngine


DEFAULT_FILTER_PARAMS = {
    "portfolio_filter.basic.ignore_st": True,
    "portfolio_filter.trend.moving_average.window_1": 20,
    "portfolio_filter.trend.moving_average.window_2": 70,
    "portfolio_filter.trend.moving_average.window_3": 150,
}


class ScreeningService:
    def run_screen(
        self,
        as_of_date: date,
        *,
        ignore_st: bool = True,
        ma_window_1: int = 20,
        ma_window_2: int = 70,
        ma_window_3: int = 150,
        trend_filter: str | None = None,
    ) -> list[dict]:
        parameters = {
            "portfolio_filter.basic.ignore_st": ignore_st,
            "portfolio_filter.trend.moving_average.window_1": ma_window_1,
            "portfolio_filter.trend.moving_average.window_2": ma_window_2,
            "portfolio_filter.trend.moving_average.window_3": ma_window_3,
        }
        engine = StockTradeDataEngine()
        pf = PortfolioFilter(engine, parameters)
        df = pf.filter(as_of_date)
        if trend_filter:
            df = df[df["trend"] == trend_filter]
        df = df.sort_values(by=["gradient"], ascending=False)
        records = []
        for _, row in df.iterrows():
            d = row.to_dict()
            if hasattr(d.get("date"), "isoformat"):
                d["date"] = d["date"].isoformat()
            records.append(d)
        return records
