import csv
import io
import json
from datetime import date, datetime, timedelta
from ledger.db import get_db, row_to_dict
from ledger.parser import canonical_name


def get_price_map():
    rows = get_db().execute("SELECT * FROM price_list").fetchall()
    return {(r["school_level"], r["fabric_type"], r["item_type"]): row_to_dict(r) for r in rows}


def enrich_item_prices(items: list[dict]) -> list[dict]:
    price_map = get_price_map()
    enriched = []
    for item in items:
        key = (item["school_level"], item["fabric_type"], item["item_type"])
        price = price_map.get(key)
        copy = dict(item)
        if price:
            copy["unit_price"] = float(price["sell_price"])
            copy["cost_price"] = float(price["cost_price"])
            copy["unit"] = price["unit"]
        else:
            copy.setdefault("unit_price", 0)
            copy.setdefault("cost_price", 0)
            copy.setdefault("unit", "件")
        copy["category_name"] = canonical_name(copy["school_level"], copy["fabric_type"], copy["item_type"])
        enriched.append(copy)
    return enriched


def create_order(source: str, raw_text: str, items: list[dict], status: str = "confirmed", final_override: bool = False):
    db = get_db()
    items = enrich_item_prices(items)
    cur = db.execute(
        "INSERT INTO orders (source, raw_text, status, final_override) VALUES (?, ?, ?, ?)",
        (source, raw_text, status, 1 if final_override else 0),
    )
    order_id = cur.lastrowid
    for item in items:
        db.execute(
            """
            INSERT INTO order_items
            (order_id, school_level, fabric_type, item_type, size, qty, unit_price, cost_price, unit, note, return_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                item["school_level"],
                item["fabric_type"],
                item["item_type"],
                str(item.get("size") or ""),
                int(item["qty"]),
                float(item.get("unit_price") or 0),
                float(item.get("cost_price") or 0),
                item.get("unit") or "件",
                item.get("note") or "",
                1 if item.get("return_flag") else 0,
            ),
        )
    db.commit()
    return get_order(order_id)


def get_order(order_id: int):
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        return None
    items = db.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,)).fetchall()
    result = row_to_dict(order)
    result["items"] = [row_to_dict(i) | {"category_name": canonical_name(i["school_level"], i["fabric_type"], i["item_type"])} for i in items]
    result["total_qty"] = sum(i["qty"] for i in result["items"])
    result["total_amount"] = round(sum(i["qty"] * i["unit_price"] for i in result["items"]), 2)
    result["gross_profit"] = round(sum(i["qty"] * (i["unit_price"] - i["cost_price"]) for i in result["items"]), 2)
    return result


def list_orders(date_filter: str | None = None, limit: int = 100):
    db = get_db()
    params = []
    sql = "SELECT * FROM orders"
    if date_filter:
        sql += " WHERE date(created_at) = ?"
        params.append(date_filter)
    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)
    rows = db.execute(sql, params).fetchall()
    return [get_order(r["id"]) for r in rows]


def delete_order(order_id: int):
    db = get_db()
    db.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    db.commit()


def stats(range_name: str = "day"):
    db = get_db()
    today = date.today()
    if range_name == "week":
        start = today - timedelta(days=6)
    elif range_name == "month":
        start = today.replace(day=1)
    else:
        start = today
    rows = db.execute(
        """
        SELECT date(o.created_at) day, oi.school_level, oi.fabric_type, oi.item_type,
               oi.size, SUM(oi.qty) qty, SUM(oi.qty * oi.unit_price) sales,
               SUM(oi.qty * (oi.unit_price - oi.cost_price)) profit
        FROM order_items oi JOIN orders o ON o.id = oi.order_id
        WHERE date(o.created_at) >= ?
        GROUP BY day, oi.school_level, oi.fabric_type, oi.item_type, oi.size
        ORDER BY day
        """,
        (start.isoformat(),),
    ).fetchall()
    daily = {}
    sku = {}
    totals = {"qty": 0, "sales": 0.0, "profit": 0.0}
    for r in rows:
        d = daily.setdefault(r["day"], {"day": r["day"], "qty": 0, "sales": 0.0, "profit": 0.0})
        d["qty"] += r["qty"]
        d["sales"] += r["sales"]
        d["profit"] += r["profit"]
        name = canonical_name(r["school_level"], r["fabric_type"], r["item_type"])
        sku[name] = sku.get(name, 0) + r["qty"]
        totals["qty"] += r["qty"]
        totals["sales"] += r["sales"]
        totals["profit"] += r["profit"]
    for collection in (daily.values(), [totals]):
        for item in collection:
            item["sales"] = round(item["sales"], 2)
            item["profit"] = round(item["profit"], 2)
    return {"range": range_name, "start": start.isoformat(), "daily": list(daily.values()), "sku_distribution": sku, "totals": totals}


def export_csv(date_filter: str | None = None):
    orders = list_orders(date_filter=date_filter, limit=100000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["订单ID", "时间", "来源", "学段", "面料", "款式", "尺码", "数量", "单位", "售价", "进货价", "销售额", "毛利", "备注"])
    for order in orders:
        for item in order["items"]:
            writer.writerow([
                order["id"], order["created_at"], order["source"], item["school_level"], item["fabric_type"], item["item_type"], item["size"], item["qty"], item["unit"], item["unit_price"], item["cost_price"], round(item["qty"] * item["unit_price"], 2), round(item["qty"] * (item["unit_price"] - item["cost_price"]), 2), item.get("note") or "",
            ])
    return output.getvalue()


def save_reconciliation(name: str, our_items: list[dict], their_items: list[dict], status: str):
    db = get_db()
    cur = db.execute(
        "INSERT INTO reconciliation_sets (name, date, our_items_json, their_items_json, status) VALUES (?, ?, ?, ?, ?)",
        (name, datetime.now().date().isoformat(), json.dumps(our_items, ensure_ascii=False), json.dumps(their_items, ensure_ascii=False), status),
    )
    db.commit()
    return cur.lastrowid
