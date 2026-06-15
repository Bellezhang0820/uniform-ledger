# 校服店记账对账中枢

手机优先的 H5 SPA + Flask + SQLite 单人记账对账工具，支持速记/语音/上传识别入账、统一账本、统计、自动对账、价目表维护和 CSV 导出。

## 本地运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

浏览器打开 `http://127.0.0.1:5000`。

## 测试

```bash
pip install -r requirements.txt
pytest -q
```

## OCR 依赖

图片 OCR 使用 Tesseract。服务器需安装 tesseract 和中文包 `chi_sim`。文本、CSV、XLSX 上传不依赖 OCR，可直接解析。

## API

- `POST /api/parse` 文本解析，不入库
- `POST /api/orders` 创建订单
- `GET /api/orders?date=YYYY-MM-DD` 查询订单
- `DELETE /api/orders/:id` 删除订单
- `POST /api/ocr` 上传图片/文本/CSV/XLSX 识别
- `POST /api/reconcile` 执行对账
- `GET /api/stats?range=day|week|month` 获取统计
- `GET /api/price-list` 查询价目表
- `PUT /api/price-list/:id` 修改售价/进货价
- `POST /api/export` 导出 CSV

## 数据

默认 SQLite 数据库位于 `data/ledger.db`。可通过环境变量 `LEDGER_DB=/path/to/db.sqlite` 指定。
