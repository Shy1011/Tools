# -*- coding: utf-8 -*-
"""
OP.GG ARAM: Mayhem 数据抓取与解析（仅使用 Python 标准库）。

数据来源: https://op.gg/zh-cn/lol/modes/aram-mayhem/<champion>/{items,runes,skills,augments}
页面为 Next.js App Router 服务端渲染，结构化数据内嵌在 __next_f RSC 流中。
"""

import json
import re
import time
import urllib.request

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
BASE = "https://op.gg/zh-cn/lol/modes/aram-mayhem"
CHAMPIONS_URL = "https://op.gg/zh-cn/lol/champions"

PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')
PATCH_RE = re.compile(r"/lol/([\d.]+)/")

SECTION_TITLES = ("核心装备", "鞋子", "出门装", "装备")


def unescape_js(s):
    """解码 JS 字符串字面量内容（\" \\ \\n \\uXXXX 等）。"""
    out = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        i += 1
        if i >= n:
            break
        e = s[i]
        if e == "u":
            out.append(chr(int(s[i + 1 : i + 5], 16)))
            i += 5
        elif e == "n":
            out.append("\n")
            i += 1
        elif e == "t":
            out.append("\t")
            i += 1
        elif e == "r":
            out.append("\r")
            i += 1
        else:
            out.append(e)
            i += 1
    return "".join(out)


def fetch(url, timeout=30):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_flight(html):
    return "".join(unescape_js(m.group(1)) for m in PUSH_RE.finditer(html))


def iter_rows(flight):
    """遍历 RSC 流中的 JSON 行。"""
    for line in flight.split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        num, _, rest = line.partition(":")
        if not num or not (rest.startswith("{") or rest.startswith("[")):
            continue
        try:
            yield json.loads(rest)
        except Exception:
            continue


def find_dict(o, pred):
    """深度优先查找第一个满足 pred 的 dict。"""
    if isinstance(o, dict):
        if pred(o):
            return o
        for v in o.values():
            r = find_dict(v, pred)
            if r is not None:
                return r
    elif isinstance(o, list):
        for v in o:
            r = find_dict(v, pred)
            if r is not None:
                return r
    return None


def collect_texts(o, out):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "children":
                collect_texts(v, out)
            elif k in ("className", "style", "src", "alt", "href", "id", "key", "name"):
                continue
            else:
                collect_texts(v, out)
    elif isinstance(o, list):
        for v in o:
            collect_texts(v, out)
    elif isinstance(o, str):
        t = o.strip()
        if t:
            out.append(t)


def norm_num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        return float(str(v).replace(",", "").replace("$undefined", ""))
    except Exception:
        return None


def norm_item(d):
    return {
        "id": d.get("id"),
        "name": d.get("name"),
        "img": d.get("image_url"),
    }


def parse_items_page(flight):
    """items 页：核心出装 / 鞋子 / 出门装 / 装备统计。"""
    sections = {"核心装备": [], "鞋子": [], "出门装": [], "装备": []}
    for row in iter_rows(flight):
        props = find_dict(row, lambda d: isinstance(d.get("data"), list) and d.get("mode") == "aram_mayhem")
        if props is None:
            continue
        texts = []
        collect_texts(row, texts)
        title = next((t for t in SECTION_TITLES if t in texts), None)
        if title is None:
            continue
        entries = []
        for e in props["data"]:
            entry = {
                "pick_rate": round(norm_num(e.get("pick_rate")) or 0, 2),
                "play": int(norm_num(e.get("play")) or 0),
                "win_rate": round(norm_num(e.get("win_rate")) or 0, 2),
            }
            if "metaBuildItems" in e and e["metaBuildItems"]:
                entry["items"] = [norm_item(x) for x in e["metaBuildItems"]]
            elif "metaStarterItems" in e and e["metaStarterItems"]:
                items = []
                for pair in e["metaStarterItems"]:
                    if isinstance(pair, list) and pair and isinstance(pair[0], dict):
                        it = norm_item(pair[0])
                        it["count"] = pair[1] if len(pair) > 1 else 1
                        items.append(it)
                entry["items"] = items
            elif "metaItem" in e and e["metaItem"]:
                it = norm_item(e["metaItem"])
                entry["item"] = it
                entry["items"] = [it]
            entries.append(entry)
        sections[title] = entries
    return sections


def parse_runes_page(flight):
    """runes 页：rune_pages 结构化数据。"""
    for row in iter_rows(flight):
        props = find_dict(row, lambda d: "rune_pages" in d)
        if props is None:
            continue
        pages = []
        for page in props.get("rune_pages", []):
            if not page.get("builds"):
                continue
            b = page["builds"][0]  # 每个符文页取最常用的一套
            active_runes = []
            for tree in (b.get("main_runes") or []) + (b.get("sub_runes") or []):
                for opt in tree or []:
                    if opt.get("isActive") and isinstance(opt, dict):
                        active_runes.append(
                            {"id": opt.get("id"), "name": opt.get("name"), "img": opt.get("image_url")}
                        )
            shards = []
            for tree in b.get("shards") or []:
                for opt in tree or []:
                    if opt.get("isActive") and isinstance(opt, dict):
                        shards.append(
                            {"id": opt.get("id"), "name": opt.get("name"), "img": opt.get("image_url")}
                        )
            primary = b.get("primary_perk_style") or {}
            secondary = b.get("perk_sub_style") or {}
            pages.append(
                {
                    "id": page.get("id"),
                    "keystone_id": (active_runes[0].get("id") if active_runes else None),
                    "primary": {
                        "id": primary.get("id"),
                        "name": primary.get("name"),
                        "img": primary.get("image_url"),
                    },
                    "secondary": {
                        "id": secondary.get("id"),
                        "name": secondary.get("name"),
                        "img": secondary.get("image_url"),
                    },
                    "runes": active_runes,
                    "shards": shards,
                    "pick_rate": round(norm_num(b.get("pick_rate")) or 0, 2),
                    "play": int(norm_num(b.get("play")) or 0),
                    "win": int(norm_num(b.get("win")) or 0),
                    "win_rate": round(norm_num(b.get("win_rate")) or 0, 2),
                }
            )
        return {"pages": pages}
    return {"pages": []}


def parse_skills_page(flight):
    """skills 页：技能加点顺序。"""
    for row in iter_rows(flight):
        props = find_dict(row, lambda d: "skill_masteries" in d)
        if props is None:
            continue
        masteries = []
        for sm in props.get("skill_masteries", []):
            if not sm.get("builds"):
                continue
            b = sm["builds"][0]
            skills = b.get("skills") or sm.get("skills") or []
            masteries.append(
                {
                    "ids": sm.get("ids") or [],
                    "order": b.get("order") or [],
                    "skills": [
                        {"key": s.get("key"), "name": s.get("name"), "img": s.get("image_url")}
                        for s in skills
                        if isinstance(s, dict)
                    ],
                    "pick_rate": round(norm_num(b.get("pick_rate")) or 0, 2),
                    "play": int(norm_num(b.get("play")) or 0),
                    "win_rate": round(norm_num(b.get("win_rate")) or 0, 2),
                }
            )
        return {"masteries": masteries}
    return {"masteries": []}


def parse_augments_page(flight):
    """augments 页：强化符文列表。"""
    for row in iter_rows(flight):
        props = find_dict(
            row,
            lambda d: isinstance(d.get("data"), list)
            and d["data"]
            and isinstance(d["data"][0], dict)
            and "largeIcon" in d["data"][0],
        )
        if props is None:
            continue
        augs = []
        for a in props["data"]:
            augs.append(
                {
                    "id": a.get("id"),
                    "key": a.get("key"),
                    "name": a.get("name"),
                    "tier": a.get("tier"),
                    "rarity": a.get("rarity"),
                    "performance": round(norm_num(a.get("performance")) or 0, 2),
                    "popular": round(norm_num(a.get("popular")) or 0, 2),
                    "icon": a.get("largeIcon") or a.get("smallIcon"),
                    "desc": a.get("desc"),
                }
            )
        augs.sort(key=lambda x: (x["tier"], x["performance"]), reverse=True)
        return {"augments": augs}
    return {"augments": []}


def parse_champions_page(flight):
    """英雄列表页：slug / 中文名 / 图标。"""
    for row in iter_rows(flight):
        props = find_dict(
            row,
            lambda d: isinstance(d.get("data"), list)
            and d["data"]
            and isinstance(d["data"][0], dict)
            and "key" in d["data"][0]
            and "/champion/" in str(d["data"][0].get("image_url", "")),
        )
        if props is None:
            continue
        champs = []
        for c in props["data"]:
            champs.append(
                {
                    "key": c.get("key"),
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "img": c.get("image_url"),
                }
            )
        champs.sort(key=lambda x: (x["name"] or ""))
        return champs
    return []


def get_champions():
    html = fetch(CHAMPIONS_URL)
    return parse_champions_page(extract_flight(html))


def get_champion_data(slug, delay=0.3):
    """抓取某英雄 ARAM Mayhem 全部数据。"""
    result = {"champion": None, "patch": None}
    for tab, parser in (
        ("items", parse_items_page),
        ("runes", parse_runes_page),
        ("skills", parse_skills_page),
        ("augments", parse_augments_page),
    ):
        html = fetch(f"{BASE}/{slug}/{tab}")
        flight = extract_flight(html)
        result[tab] = parser(flight)
        if result["patch"] is None:
            m = PATCH_RE.search(html)
            if m:
                result["patch"] = m.group(1)
        time.sleep(delay)
    return result
