from ledger.parser import aggregate_items, canonical_name


def compare_items(our_items: list[dict], their_items: list[dict]) -> dict:
    ours = aggregate_items(our_items, reconcile=True)
    theirs = aggregate_items(their_items, reconcile=True)
    rows = []
    all_keys = sorted(set(ours) | set(theirs), key=lambda x: (x[0] or '', x[1] or '', x[2] or '', x[3] or ''))
    for key in all_keys:
        our = ours.get(key)
        their = theirs.get(key)
        our_qty = int(our.get("qty", 0)) if our else 0
        their_qty = int(their.get("qty", 0)) if their else 0
        ref = our or their or {}
        unit_price = float(ref.get("unit_price") or 0)
        diff_qty = our_qty - their_qty
        if our and their and diff_qty == 0:
            status = "一致"
            mark = "✅"
        elif our and their:
            status = "数量不符"
            mark = "⚠️"
        else:
            status = "我方多" if our else "对方多"
            mark = "❌"
        rows.append({
            "key": "|".join(str(k) for k in key),
            "category_name": canonical_name(key[0], key[1], key[2]) if key[0] and key[1] and key[2] else ref.get("category_name", ""),
            "school_level": key[0],
            "fabric_type": key[1],
            "item_type": key[2],
            "size": key[3],
            "our_qty": our_qty,
            "their_qty": their_qty,
            "diff_qty": diff_qty,
            "diff_amount": round(diff_qty * unit_price, 2),
            "unit_price": unit_price,
            "status": status,
            "mark": mark,
        })
    summary = {
        "total": len(rows),
        "matched": sum(1 for r in rows if r["status"] == "一致"),
        "mismatched": sum(1 for r in rows if r["status"] != "一致"),
        "diff_amount": round(sum(r["diff_amount"] for r in rows), 2),
    }
    return {"rows": rows, "summary": summary}
