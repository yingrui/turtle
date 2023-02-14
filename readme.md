# Turtle

Turtle is a private trade system

## Installation

Please read env.md to prepare Python environment and Database.

## Data Collection

Run scripts to download data from tushare.
```bash
python3 dataset/update_stock_list.py
python3 dataset/update_stock_trade_daily.py --start 2015-01-01
python3 dataset/update_trade_calendar.py
```

Run scripts to update daily.

```bash
python3 dataset/update_stock_list.py
python3 dataset/update_stock_trade_daily.py
```

If throw no module found error, please add PYTHONPATH environment variable.
```bash
PYTHONPATH=. python3 dataset/update_stock_list.py
```

## Simulation

Run scripts to simulate
```bash
python3 simulation/main.py
```