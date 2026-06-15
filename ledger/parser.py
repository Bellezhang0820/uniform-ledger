import re
from dataclasses import dataclass
from typing import Iterable

PRICE_SEED = [
    ("小学", "速干", "短袖", 35, "件"),
    ("小学", "速干", "长裤", 35, "条"),
    ("小学", "速干", "短裤", 30, "条"),
    ("小学", "速干", "套装", 75, "套"),
    ("小学", "同款", "短袖", 35, "件"),
    ("小学", "同款", "长裤", 35, "条"),
    ("小学", "春季", "长裤", 35, "条"),
    ("小学", "涤棉", "长裤", 30, "条"),
    ("中学", "速干", "短袖", 40, "件"),
    ("中学", "速干", "长裤", 40, "条"),
    ("中学", "速干", "套装", 75, "套"),
    ("中学", "同款", "短袖", 38, "件"),
    ("中学", "同款", "长裤", 38, "条"),
    ("中学", "同款夏", "长裤", 38, "条"),
    ("中学", "冰感棉夏", "长裤", 38, "条"),
    ("中学", "凉感", "短袖", 45, "件"),
    ("中学", "网眼", "短袖", 38, "件"),
    ("中学", "冰丝", "短袖", 40, "件"),
    ("中学", "冰丝", "长裤", 40, "条"),
]

PRICE_MAP = {(a, b, c): {"sell_price": float(d), "cost_price": round(float(d) * 0.7, 2), "unit": e} for a, b, c, d, e in PRICE_SEED}

FABRICS = ["冰感棉夏", "同款夏", "学校同款", "速干", "同款", "春季", "涤棉", "冰感棉", "凉感", "网眼", "冰丝", "夏"]
ITEM_TYPES = ["短袖", "长裤", "短裤", "套装"]
SIZE_RE = r"(1[1-9]0|2[0-1]0|1[2-9]5)"

@dataclass
class ParseContext:
    school_level: str | None = None
    fabric_type: str | None = None
    item_type: str | None = None
    final_override: bool = False

    def category(self):
        if self.school_level and self.fabric_type and self.item_type:
            return self.school_level, self.fabric_type, self.item_type
        return None


def unit_for_item(item_type: str) -> str:
    if item_type == "套装":
        return "套"
    if item_type == "短袖":
        return "件"
    return "条"


def canonical_name(school_level: str, fabric_type: str, item_type: str) -> str:
    return f"{school_level}{fabric_type}{item_type}"


def infer_school(text: str, context_level: str | None = None) -> str:
    if "中学" in text or any(k in text for k in ["冰丝", "凉感", "网眼", "冰感棉"]):
        return "中学"
    if "小学" in text:
        return "小学"
    return context_level or "小学"


def normalize_category(text: str, context: ParseContext | None = None) -> dict | None:
    context = context or ParseContext()
    original = text
    text = re.sub(r"[（(].*?[）)]", "", text)
    text = text.replace(" ", "")
    if not text:
        return None

    school = infer_school(text, context.school_level)
    if "学校同款" in original and "夏长裤" in original and school == "中学":
        return {"school_level": "中学", "fabric_type": "同款夏", "item_type": "长裤"}

    fabric = None
    if "冰感棉" in text:
        fabric = "冰感棉夏" if "夏" in text or "长裤" in text else "冰感棉"
    elif "同款夏" in text or ("夏长裤" in text and "同款" in original):
        fabric = "同款夏"
    elif "学校同款" in text or "同款" in text:
        fabric = "同款"
    elif "春季" in text:
        fabric = "春季"
    elif "涤棉" in text:
        fabric = "涤棉"
    elif "凉感" in text:
        fabric = "凉感"
    elif "网眼" in text:
        fabric = "网眼"
    elif "冰丝" in text:
        fabric = "冰丝"
    elif "速干" in text:
        fabric = "速干"
    elif "夏长裤" in text and school == "中学":
        fabric = "同款夏"
    else:
        fabric = context.fabric_type

    item = None
    for candidate in ITEM_TYPES:
        if candidate in text:
            item = candidate
            break
    if not item and "学校同款" in original:
        item = "短袖"
    if not item:
        item = context.item_type

    if not (school and fabric and item):
        return None

    key = (school, fabric, item)
    if key not in PRICE_MAP:
        # Prefer the nearest valid school-level category for ambiguous handwritten text.
        fallback_key = (school, fabric.replace("夏", "") if fabric != "同款夏" else fabric, item)
        if fallback_key in PRICE_MAP:
            fabric = fallback_key[1]
        elif (school, "速干", item) in PRICE_MAP and fabric in {None, "夏"}:
            fabric = "速干"
        elif (school, "同款", item) in PRICE_MAP and fabric == "学校同款":
            fabric = "同款"
    return {"school_level": school, "fabric_type": fabric, "item_type": item}


def normalize_for_reconcile(item: dict) -> tuple:
    fabric = item.get("fabric_type") or ""
    if fabric == "冰丝":
        fabric = "速干"
    return (item.get("school_level"), fabric, item.get("item_type"), str(item.get("size") or ""))


def _note_from_text(text: str) -> str:
    notes = re.findall(r"[（(](.*?)[）)]", text)
    return "；".join(n.strip() for n in notes if n.strip())


def _make_item(category: dict, size: str, qty: int, note: str = "") -> dict:
    key = (category["school_level"], category["fabric_type"], category["item_type"])
    price = PRICE_MAP.get(key, {"sell_price": 0.0, "cost_price": 0.0, "unit": unit_for_item(category["item_type"])})
    return {
        "school_level": category["school_level"],
        "fabric_type": category["fabric_type"],
        "item_type": category["item_type"],
        "category_name": canonical_name(category["school_level"], category["fabric_type"], category["item_type"]),
        "size": str(size),
        "qty": int(qty),
        "unit_price": float(price["sell_price"]),
        "cost_price": float(price["cost_price"]),
        "unit": price.get("unit") or unit_for_item(category["item_type"]),
        "note": note,
    }


def _update_context(context: ParseContext, category: dict | None):
    if category:
        context.school_level = category["school_level"]
        context.fabric_type = category["fabric_type"]
        context.item_type = category["item_type"]


def _parse_platform_line(line: str, context: ParseContext) -> list[dict]:
    m = re.search(r"(?P<qty>\d+)\s*[【\[]\s*(?P<size>\d{2,3})(?:\s*尺码)?\s*[】\]]\s*(?P<desc>.+)", line)
    if not m:
        return []
    desc = m.group("desc")
    category = normalize_category(desc, context)
    _update_context(context, category)
    if not category:
        return []
    return [_make_item(category, m.group("size"), int(m.group("qty")), _note_from_text(desc))]


def _parse_each_line(line: str, context: ParseContext) -> list[dict]:
    m = re.search(rf"(?P<sizes>(?:{SIZE_RE}\s*){{2,}})各\s*(?P<qty>\d+)\s*(?:件|条|套)?", line)
    if not m or not context.category():
        return []
    category = {"school_level": context.school_level, "fabric_type": context.fabric_type, "item_type": context.item_type}
    return [_make_item(category, size, int(m.group("qty")), _note_from_text(line)) for size in re.findall(SIZE_RE, m.group("sizes"))]


def _category_fragment_around(token: str) -> str:
    return re.sub(rf"{SIZE_RE}|\d+|[*xX×/、,，\s]|件|条|套|各", "", token)


def _parse_qty_patterns(line: str, context: ParseContext) -> list[dict]:
    items = []
    line = line.replace("×", "*").replace("x", "*").replace("X", "*")
    base_category = normalize_category(line, context)
    if base_category:
        _update_context(context, base_category)
    category = base_category or ({"school_level": context.school_level, "fabric_type": context.fabric_type, "item_type": context.item_type} if context.category() else None)

    for token in re.split(r"[/、,，;；\n]+", line):
        token = token.strip()
        if not token:
            continue
        cat = normalize_category(token, context) or category
        for m in re.finditer(rf"(?P<size>{SIZE_RE})\s*[*]\s*(?P<qty>\d+)\s*(?:件|条|套)?", token):
            if cat:
                items.append(_make_item(cat, m.group("size"), int(m.group("qty")), _note_from_text(line)))
        if re.search(r"[*]", token):
            continue
        for m in re.finditer(rf"(?P<size>{SIZE_RE})\s*(?P<frag>[\u4e00-\u9fff]*?)\s*(?P<qty>\d+)\s*(?:件|条|套)", token):
            frag = m.group("frag")
            cat = normalize_category(frag, context) if frag else cat
            if cat:
                items.append(_make_item(cat, m.group("size"), int(m.group("qty")), _note_from_text(line)))
    return items


def _parse_category_qty_no_size(line: str, context: ParseContext) -> list[dict]:
    m = re.search(r"(?P<qty>\d+)\s*(件|条|套)$", line)
    if not m:
        return []
    prefix = line[:m.start()]
    category = normalize_category(prefix, context)
    if not category:
        return []
    _update_context(context, category)
    return [_make_item(category, "", int(m.group("qty")), _note_from_text(line))]


def _looks_like_size_detail(line: str) -> bool:
    line = line.strip().replace("×", "*").replace("x", "*").replace("X", "*")
    return bool(re.search(rf"^{SIZE_RE}\s*[*]\s*\d+", line) or re.search(rf"^(?:{SIZE_RE}\s*){{2,}}各\s*\d+", line))


def _is_total_header(line: str, next_line: str, context: ParseContext) -> bool:
    m = re.search(r"(?P<qty>\d+)\s*(件|条|套)$", line)
    if not m or re.search(SIZE_RE, line) or not _looks_like_size_detail(next_line):
        return False
    return normalize_category(line[:m.start()], context) is not None


def parse_text(raw_text: str) -> dict:
    context = ParseContext()
    parsed: list[dict] = []
    errors: list[str] = []
    lines = [line.strip() for line in (raw_text or "").splitlines()]
    for idx, line in enumerate(lines):
        if not line:
            continue
        if "以此为准" in line:
            context.final_override = True
            line = line.replace("以此为准", "")
        next_line = next((candidate for candidate in lines[idx + 1:] if candidate), "")
        if _is_total_header(line, next_line, context):
            qty_pos = re.search(r"\d+\s*(件|条|套)$", line).start()
            _update_context(context, normalize_category(line[:qty_pos], context))
            continue
        before = len(parsed)
        for parser in (_parse_platform_line, _parse_each_line, _parse_qty_patterns, _parse_category_qty_no_size):
            found = parser(line, context)
            if found:
                parsed.extend(found)
                break
        if len(parsed) == before:
            category = normalize_category(line, context)
            if category:
                _update_context(context, category)
            else:
                errors.append(line)
    return {"items": parsed, "errors": errors, "final_override": context.final_override}


def aggregate_items(items: Iterable[dict], reconcile: bool = False) -> dict[tuple, dict]:
    grouped: dict[tuple, dict] = {}
    for item in items:
        key = normalize_for_reconcile(item) if reconcile else (item.get("school_level"), item.get("fabric_type"), item.get("item_type"), str(item.get("size") or ""))
        if key not in grouped:
            grouped[key] = dict(item, qty=0)
        grouped[key]["qty"] += int(item.get("qty") or 0)
    return grouped
