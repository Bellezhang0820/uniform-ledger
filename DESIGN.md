# 校服店记账对账中枢 - DESIGN

## Project Architecture Overview

本项目是手机优先的 H5 SPA + Python Flask + SQLite 单人记账系统。

- Frontend: `static/index.html`, `static/app.js`, `static/styles.css`
  - Vanilla JS SPA, 5 个底部 Tab: 入账、账本、统计、对账、设置
  - Tailwind CSS CDN, Chart.js CDN, Material Symbols 图标
  - Web Speech API 用于语音转文字，所有解析结果进入确认表单后再提交
  - 图片/截图/Excel 上传走后端 OCR/导入接口，前端展示结构化结果后确认入账
- Backend: `app.py`, `ledger/`
  - Flask REST JSON API
  - SQLite 数据库，默认文件 `data/ledger.db`
  - 文本解析、SKU 归一、对账、统计、导出都放在可测试的 Python 模块中
- Tests: `tests/test_app.py`
  - pytest 覆盖文本解析、SKU 归一、对账、金额计算和主要 API

## File Structure Plan

```text
uniform-ledger/
  app.py                    # Flask app factory and API endpoints
  requirements.txt          # Python dependencies
  README.md                 # Deployment and usage guide
  DESIGN.md                 # Architecture/design document
  ledger/
    __init__.py
    db.py                   # SQLite schema, connection, seed price list
    parser.py               # Chinese shorthand parser and SKU normalization
    reconciliation.py       # Reconciliation comparison logic
    services.py             # Order, stats, export service functions
  static/
    index.html              # Mobile-first SPA shell
    app.js                  # Frontend state, API calls, charts, speech UI
    styles.css              # Design tokens and focused overrides
  tests/
    test_app.py             # At least 10 pytest cases
```

## Key Design Decisions

1. 人在环优先: `/api/parse` and `/api/ocr` never persist orders. They return structured draft items for user confirmation/edit/delete, then `/api/orders` creates the final ledger entry.
2. One raw input to many SKU rows: `orders.raw_text` stores the original text and `order_items` stores parsed normalized SKU rows.
3. Price list is authoritative for sell/cost price: seed includes all 19 required categories; default cost price is 70% of sell price and can be edited through API/UI.
4. Parser is deterministic and testable: it tracks school level/category context across lines, supports `*`, `x`, `各`, platform formats like `3【120】...`, and mixed lines such as `170短袖2件`.
5. Reconciliation compares normalized SKU keys: school level + fabric type + item type + size. Per requirement, `冰丝` is normalized into `速干` only for reconciliation.
6. UI follows the provided institutional ledger tokens but resolves conflicts in favor of this product brief: light background `#f9f9fb`, black/white primary palette, Inter + JetBrains Mono, max-width 430px centered mobile shell, bottom tab bar, and compact `0.25rem` radius.
7. Export supports CSV directly without extra heavy dependencies. The endpoint is named `/api/export` and returns `text/csv` for backup/interchange.
8. OCR uses `pytesseract` when available. Excel/CSV/TXT imports are accepted through `/api/ocr`; `.xlsx` is parsed with `openpyxl` when installed.
