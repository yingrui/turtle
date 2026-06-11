import os

os.environ.setdefault("DB_URL", "sqlite:///./test_stock.db")
os.environ.setdefault("STOCK_SECRET_KEY", "test-secret")
os.environ.setdefault("STOCK_LOGS_DIR", os.path.join(os.path.dirname(__file__), "../../logs"))
