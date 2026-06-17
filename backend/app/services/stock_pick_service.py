from app.core.engine import stock_pick


class StockPickService:
    def pick_stocks(self, **kwargs) -> dict:
        return stock_pick.pick_stocks(**kwargs)

    def get_presets(self) -> list[dict]:
        return stock_pick.get_presets()
