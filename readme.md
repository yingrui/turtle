# 个人海龟交易系统 Turtle

本项目期望能为个人提供一个基于《海龟交易法则》的简单交易系统，帮助大家能够针对中国股票市场进行分析。

Turtle is a simple trade system based on a book named "Turtle Trading Rules".

## 安装 Installation
请参考[env.md](env.md)准备Python环境和数据库。

Please read [env.md](env.md) to prepare Python environment and Database.

## 数据收集 Data Collection
第一次运行系统时，运行以下脚本，从tushare下载数据。

Run scripts to download data from tushare when you first run the system.
```bash
PYTHONPATH=. python3 dataset/update_stock_trade_daily.py --start 2015-01-01
PYTHONPATH=. python3 dataset/update_trade_calendar.py
```
每天收盘后运行以下脚本，更新当日的数据。

Run scripts to update daily.

```bash
PYTHONPATH=. python3 dataset/update_stock_trade_daily.py
```
注意: 如果出现找不到模块的错误，请检查并添加PYTHONPATH环境变量。

Note: If throw no module found error, please add PYTHONPATH environment variable.

## 回测 Simulation
运行以下脚本进行回测。

Run scripts to simulate
```bash
PYTHONPATH=. python3 simulation/main.py
```
可以指定不同的投资组合和开始时间并进行回测。

You can specify different portfolio and start time to simulate.
```bash
PYTHONPATH=. python3 simulation/main.py --configure test.yaml --start-date 2022-01-01
```

### 设置投资组合以及回测参数 Set Portfolio and Simulation Parameters
请参考[portfolio.yaml](portfolio.yaml)来设置个人投资组合。
```yaml
---
name: portfolio
start_date: 2023-02-17
initial_investment: 250000
follow_stocks:
  - '600519.SH'  # 您可以将您关注的股票代码添加到这里
  - '000858.SZ'  
risk_control:
  bearable_trading_loss: 0.01
  position_control: 1.0
  position_control.reserve_profit: 0
  max_position_size: 50
  max_position_ratio: 0.5
  stop_loss_point.should_check: True
  stop_loss_point.n_times_atr: 2
  stop_loss_point.should_update: True
  max_holding_period.should_check: True
  max_holding_period.days: 80
policies:
  - trade_policy.name: moving_average
    trade_policy.moving_average.triple: False
    trade_policy.moving_average.window_1: 10
    trade_policy.moving_average.window_2: 60
    trade_policy.moving_average.should_price_higher_than_ma: True
  - trade_policy.name: donchian
    trade_policy.donchian.ma_window_1: 20
    trade_policy.donchian.ma_window_2: 70
    trade_policy.donchian.up_days: 20
    trade_policy.donchian.down_days: 10
  - trade_policy.name: moving_average
    trade_policy.moving_average.triple: True
    trade_policy.moving_average.window_1: 10
    trade_policy.moving_average.window_2: 60
    trade_policy.moving_average.window_3: 70
  - trade_policy.name: ensemble
    trade_policy.moving_average.triple: False
    trade_policy.moving_average.window_1: 10
    trade_policy.moving_average.window_2: 60
    trade_policy.donchian.ma_window_1: 20
    trade_policy.donchian.ma_window_2: 70
    trade_policy.donchian.up_days: 20
    trade_policy.donchian.down_days: 10
  - trade_policy.name: atr
    trade_policy.atr.ma_days: 30
    trade_policy.atr.atr_days: 20
    trade_policy.atr.up: 3
    trade_policy.atr.down: 1
  - trade_policy.name: bolling
    trade_policy.bolling.ma_days: 30
    trade_policy.bolling.up: 2
    trade_policy.bolling.down: 1.5
```