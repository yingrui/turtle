## Installation

1. Prepare Python environment
2. Prepare RDBMS (MySQL)

### Python Environment

```bash
conda create -n stock python=3.8
```

### Packages

```bash
pip install tushare
pip install python-dotenv
pip install sqlalchemy
pip install pymysql
pip install cryptography
pip install pyyaml
pip install statsmodels
```

### Environment Variables

Create .env file, and input your own sensitive information.

```text
TUSHARE_TOKEN={your-tushare-token}
DB_URL=mysql+pymysql://{username}:{password}@{host}/{databasename}
```

### MySQL

```bash
docker run --name turtle-mysql -e MYSQL_ROOT_PASSWORD={your-secret-pw} \
           -e MYSQL_USER={username} -e MYSQL_PASSWORD={password} \
           -e MYSQL_DATABASE={databasename} -p 3306:3306 -d mysql:8.0 \
           --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci
```

Login database with MySQL Client

```bash
mysql --user investor --password stock
```

```sql
CREATE TABLE trade_calendar (
    exchange varchar(10), 
    cal_date date, 
    is_open int, 
    pretrade_date date, 
    constraint pk_exchange_date primary key (exchange, cal_date)
);

CREATE TABLE stock (
    ts_code varchar(10), 
    symbol varchar(10), 
    name varchar(30), 
    area varchar(30),
    industry varchar (30),
    market varchar(10),
    exchange varchar(10),
    curr_type varchar(10),
    list_status char(1),
    list_date date,
    delist_date date,
    is_hs char(1),
    PRIMARY KEY (ts_code)
);

CREATE TABLE stock_trade_daily (
    ts_code varchar(10), 
    trade_date date, 
    open decimal(10,2), 
    high decimal(10,2),
    low decimal(10,2),
    close decimal(10,2),
    pre_close decimal(10,2),
    `change` decimal(10,2),
    pct_chg decimal(10,2),
    vol decimal(10,2),
    amount decimal(10,2),
    constraint pk_code_and_date primary key (ts_code, trade_date)
);

CREATE INDEX index_trade_date_on_stock_trade_daily ON stock_trade_daily (trade_date);

CREATE TABLE stock_adj_daily (
    ts_code varchar(10), 
    trade_date date, 
    adj_factor decimal(10,4),
    constraint pk_code_and_date_on_adj_daily primary key (ts_code, trade_date)
);

CREATE INDEX index_trade_date_on_stock_adj_daily ON stock_adj_daily (trade_date);

CREATE TABLE dividends (
    ts_code varchar(10), 
    end_date date,
    ann_date date, 
    div_proc varchar(24), 
    stk_div decimal(10,4),
    stk_bo_rate decimal(10,4),
    stk_co_rate decimal(10,4),
    cash_div decimal(10,4),
    cash_div_tax decimal(10,4),
    record_date date,
    ex_date date,
    pay_date date,
    div_listdate date,
    imp_ann_date date,
    base_date date,
    base_share decimal(10,4),
    update_flag varchar(12),
    constraint pk_code_and_date_on_dividends primary key (ts_code, ex_date)
);

```