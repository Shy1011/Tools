# -*- coding: utf-8 -*-
"""
静态数据生成器：抓取所有英雄的 ARAM: Mayhem 数据，生成 GitHub Pages 可用的静态 JSON。

用法:
  python generate_static.py [--out site] [--limit 3] [--delay 0.4]

生成结果:
  site/index.html              页面（自动从本目录复制）
  site/.nojekyll               禁用 Jekyll
  site/data/champions.json     英雄列表
  site/data/<slug>.json        每个英雄的完整数据
  site/data/meta.json          生成时间与统计
"""

import argparse
import io
import json
import os
import shutil
import sys
import time

import opgg_mayhem_scraper as scraper


def log(msg):
    print(msg, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="site", help="输出目录")
    ap.add_argument("--limit", type=int, default=0, help="只抓前 N 个英雄（0 = 全部，用于测试）")
    ap.add_argument("--delay", type=float, default=0.5, help="英雄之间的间隔秒数")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.abspath(args.out)
    data_dir = os.path.join(out_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    # 页面文件
    shutil.copyfile(os.path.join(here, "index.html"), os.path.join(out_dir, "index.html"))
    with io.open(os.path.join(out_dir, ".nojekyll"), "w", encoding="utf-8") as f:
        f.write("")

    log("获取英雄列表...")
    champions = scraper.get_champions()
    log(f"共 {len(champions)} 位英雄")
    if args.limit > 0:
        champions = champions[: args.limit]
        log(f"测试模式：仅处理前 {len(champions)} 位")

    with io.open(os.path.join(data_dir, "champions.json"), "w", encoding="utf-8") as f:
        json.dump(champions, f, ensure_ascii=False)
    log("已写入 data/champions.json")

    ok_count = 0
    fail_list = []
    for i, c in enumerate(champions, 1):
        slug = c["key"]
        out_path = os.path.join(data_dir, f"{slug}.json")
        data = None
        for attempt in (1, 2):  # 失败重试一次
            try:
                data = scraper.get_champion_data(slug)
                break
            except Exception as exc:
                log(f"  [{attempt}] {slug} 抓取失败: {exc}")
                if attempt == 1:
                    time.sleep(3)
        if data is None:
            fail_list.append(slug)
            log(f"  [{i}/{len(champions)}] {slug} 跳过（两次都失败）")
            continue
        data["champion"] = c
        data["fetched_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with io.open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        ok_count += 1
        if i % 10 == 0 or i == len(champions):
            log(f"  进度 {i}/{len(champions)}（成功 {ok_count}，失败 {len(fail_list)}）")
        time.sleep(args.delay)

    patch = None
    for name in os.listdir(data_dir):
        if not name.endswith(".json") or name in ("champions.json", "meta.json"):
            continue
        rec = _load(os.path.join(data_dir, name))
        if rec and rec.get("patch"):
            patch = rec["patch"]
            break

    meta = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(champions),
        "ok": ok_count,
        "failed": fail_list,
        "patch": patch,
    }
    with io.open(os.path.join(data_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    log(f"完成：成功 {ok_count}，失败 {len(fail_list)}")
    if fail_list:
        log("失败英雄: " + ", ".join(fail_list))
    log(f"输出目录: {out_dir}")


def _load(path):
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


if __name__ == "__main__":
    main()
