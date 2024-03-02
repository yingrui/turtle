# 个人海龟交易系统 Turtle

本项目期望能为个人提供一个基于《海龟交易法则》的简单交易系统。

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