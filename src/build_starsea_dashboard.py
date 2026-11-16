#!/usr/bin/env python3
"""从存档的 cosmic_starsea 构建交互式 HTML 仪表盘。

支持新版压缩存档（base64 + brotli payload）与旧版明文存档。

用法（在项目根目录）:
    # 默认：构建不含数据的空壳，可在网页里“载入 JSON”
    python src/build_starsea_dashboard.py

    # 内嵌数据：读取存档并生成自包含仪表盘
    python src/build_starsea_dashboard.py -i data/m0-slot.json
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime
from pathlib import Path

from starsea_parser import StarseaParser

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "m0-slot.json"
DEFAULT_OUTPUT = ROOT / "dist" / "starsea_dashboard.html"          # 空壳（无数据）
DEFAULT_DATA_OUTPUT = ROOT / "dist" / "starsea_dashboard_data.html"  # 内嵌数据
DEFAULT_TEMPLATE = Path(__file__).resolve().with_name("templates") / "dashboard_template.html"
BROTLI_DIR = Path(__file__).resolve().with_name("vendor") / "brotli-dec-wasm"
BROTLI_JS = BROTLI_DIR / "brotli_dec_wasm.js"
BROTLI_WASM = BROTLI_DIR / "brotli_dec_wasm_bg.wasm"


def build_rows(parser: StarseaParser) -> list[dict]:
    rows: list[dict] = []
    for aid, art in parser.artifacts.items():
        defn = art.get("definition") or {}
        desc = defn.get("descriptor") or {}
        template = defn.get("template") or {}
        system = template.get("system") or {}
        scond = system.get("conditions") or {}

        kind = defn.get("kind")
        is_star = kind == "star"

        worlds = []
        mats: set[str] = set()
        total_size = 0
        size_max = 0
        total_mine = 0
        pop_sum = 0
        solar_max = 0
        wind_max = 0
        hab_max = 0
        cap = int(scond.get("stellar_capacity_kw") or 0)

        for w in template.get("worlds") or []:
            c = w.get("conditions") or {}
            ext = c.get("extraction") or {}
            wm = {k: int(v) for k, v in (ext.get("per_material_bps") or {}).items() if v}
            wsize = int(c.get("size_bps") or 0)
            wpops = int(c.get("natural_population_capacity") or 0)
            total_size += wsize
            size_max = max(size_max, wsize)
            total_mine += sum(wm.values())
            pop_sum += wpops
            solar_max = max(solar_max, int(c.get("solar_output_bps") or 0))
            wind_max = max(wind_max, int(c.get("wind_output_bps") or 0))
            hab_max = max(hab_max, int(c.get("habitability_bps") or 0))
            if not cap:
                cap = max(cap, int(c.get("stellar_capacity_kw") or 0))
            mats.update(wm)
            worlds.append({
                "label": w.get("label"),
                "wtype": w.get("world_type"),
                "env": w.get("environment_id"),
                "bodyKind": c.get("body_kind"),
                "site": c.get("site_kind"),
                "canvas": c.get("canvas_kind"),
                "size": wsize,
                "pop": wpops,
                "hab": int(c.get("habitability_bps") or 0),
                "minePrimary": c.get("mining_primary_item"),
                "mats": wm,
            })

        # 恒星档案的本体只有恒星（definition.body_count = 1）。
        # template.worlds 是该档案生成星系的预览天体（常为 2–4 个），
        # 不计入档案本体，也不参与档案级规模/资源聚合。
        if is_star:
            mats = set()
            total_size = size_max = 0
            total_mine = pop_sum = 0
            solar_max = wind_max = hab_max = 0
            body_count = max(1, int(defn.get("body_count") or 0))
        else:
            body_count = len(worlds)

        rows.append({
            "id": aid,
            "seq": art.get("created_sequence"),
            "step": art.get("created_at_step"),
            "kind": kind,
            "rarity": defn.get("rarity"),
            "strength": desc.get("strength"),
            "origin": art.get("origin"),
            "fav": bool(art.get("favorite")),
            "seed": desc.get("seed"),
            "body": body_count,
            "syskind": defn.get("system_kind_id"),
            "sclass": defn.get("stellar_class") or system.get("stellar_class"),
            "pkind": defn.get("planet_kind_id"),
            "dist": int(system.get("distance_milli_light_years") or 0),
            "cap": cap,
            "size": total_size,
            "sizeMax": size_max,
            "mine": total_mine,
            "pops": pop_sum,
            "solar": solar_max,
            "wind": wind_max,
            "hab": hab_max,
            "matCount": len(mats),
            "mats": sorted(mats),
            "sysLabel": system.get("label"),
            "worlds": worlds,
        })
    return rows


def material_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in rows:
        for m in r["mats"]:
            counts[m] = counts.get(m, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def system_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in rows:
        k = r["syskind"] or "—"
        counts[k] = counts.get(k, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def build_payload(parser: StarseaParser, rows: list[dict]) -> dict:
    cs = parser.starsea
    kinds: dict[str, int] = {}
    rarities: dict[str, int] = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
        rarities[r["rarity"]] = rarities.get(r["rarity"], 0) + 1
    return {
        "meta": {
            "source": Path(parser.save_path).name,
            "revision": cs.get("revision"),
            "version": cs.get("version"),
            "nextBangSequence": cs.get("next_bang_sequence"),
            "nextPlacementSequence": cs.get("next_placement_sequence"),
            "artifactCount": len(rows),
            "worldCount": sum(r["body"] for r in rows),
            "saveFormat": parser.save_meta.get("format_version"),
            "saveMagic": parser.save_meta.get("save_magic"),
            "scenario": parser.save_meta.get("scenario_id"),
            "rulesVersion": parser.save_meta.get("rules_version"),
            "savedAtUtc": parser.save_meta.get("saved_at_utc"),
            "storageAlgorithm": (parser.save_meta.get("storage") or {}).get("algorithm"),
            "generatedAt": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
            "kinds": kinds,
            "rarities": rarities,
            "slots": list((cs.get("slots") or {}).keys()),
            "retiredWorldCount": len(cs.get("retired_world_ids") or []),
            "bangReceipts": len(cs.get("bang_receipts") or {}),
            "placementReceipts": len(cs.get("placement_receipts") or {}),
        },
        "materials": material_counts(rows),
        "systems": system_counts(rows),
        "rows": rows,
    }


def empty_payload() -> dict:
    """不含数据的空仪表盘 payload，可在网页中通过“载入 JSON”加载存档。"""
    return {
        "meta": {
            "source": "（未载入）",
            "revision": "—",
            "version": "—",
            "nextBangSequence": None,
            "nextPlacementSequence": None,
            "artifactCount": 0,
            "worldCount": 0,
            "saveFormat": None,
            "saveMagic": None,
            "scenario": None,
            "rulesVersion": None,
            "savedAtUtc": None,
            "storageAlgorithm": None,
            "generatedAt": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
            "kinds": {},
            "rarities": {},
            "slots": [],
            "retiredWorldCount": 0,
            "bangReceipts": 0,
            "placementReceipts": 0,
        },
        "materials": {},
        "systems": {},
        "rows": [],
    }


def brotli_assets() -> tuple[str, str]:
    """返回 (解码器 JS, wasm base64)；缺少 vendor 文件时返回空字符串。"""
    if not (BROTLI_JS.exists() and BROTLI_WASM.exists()):
        return "", ""
    js = BROTLI_JS.read_text(encoding="utf-8")
    # 该 ESM 的默认导出为 wasm 初始化函数（局部名 N），命名导出 decompress。
    init = """
const __wasmEl = document.getElementById("brotliWasm");
if (__wasmEl) {
  const __b64 = __wasmEl.textContent.trim();
  if (__b64 && !__b64.startsWith("/*__")) {
    try {
      const __bin = atob(__b64);
      const __bytes = new Uint8Array(__bin.length);
      for (let i = 0; i < __bin.length; i++) __bytes[i] = __bin.charCodeAt(i);
      window.__brotliReady = N(__bytes).then(() => ({ decompress }));
    } catch (e) {
      console.warn("Brotli decoder init failed", e);
    }
  }
}
"""
    wasm_b64 = base64.b64encode(BROTLI_WASM.read_bytes()).decode("ascii")
    return js + init, wasm_b64


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="构建 cosmic_starsea 交互式仪表盘（默认构建不含数据的空壳）")
    ap.add_argument("json_name", nargs="?", default=None,
                    help="JSON 文件名（位置参数，等价于 -i）")
    ap.add_argument("-i", "--input", default=None,
                    help=f"存档或导出的星海 JSON；提供后构建内嵌数据的仪表盘"
                         f"（如 {DEFAULT_INPUT.relative_to(ROOT)}）")
    ap.add_argument("-o", "--output", default=None,
                    help=f"输出 HTML（空壳默认 {DEFAULT_OUTPUT.relative_to(ROOT)}，"
                         f"数据版默认 {DEFAULT_DATA_OUTPUT.relative_to(ROOT)}）")
    ap.add_argument("--empty", action="store_true",
                    help="强制构建不含数据的空壳（忽略 -i）")
    ap.add_argument("--template", default=None,
                    help=f"HTML 模板（默认 {DEFAULT_TEMPLATE.relative_to(ROOT)}）")
    ap.add_argument("--data-out", default=None, help="同时输出紧凑的 JSON 数据（调试用）")
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    input_path = None if args.empty else (args.input or args.json_name)
    is_empty = not input_path
    if is_empty:
        payload = empty_payload()
        out = Path(args.output) if args.output else DEFAULT_OUTPUT
    else:
        parser = StarseaParser(input_path)
        rows = build_rows(parser)
        payload = build_payload(parser, rows)
        out = Path(args.output) if args.output else DEFAULT_DATA_OUTPUT

    template_path = Path(args.template) if args.template else DEFAULT_TEMPLATE
    template = template_path.read_text(encoding="utf-8")
    if "/*__STARSEA_DATA__*/" not in template:
        raise SystemExit(f"模板中缺少 /*__STARSEA_DATA__*/ 占位符: {template_path}")

    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    data_json = data_json.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    html = template.replace("/*__STARSEA_DATA__*/", "window.STARSEA = " + data_json + ";")

    decoder_js, wasm_b64 = brotli_assets()
    html = html.replace("/*__BROTLI_DECODER__*/", decoder_js)
    html = html.replace("/*__BROTLI_WASM_B64__*/", wasm_b64)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    if args.data_out:
        data_out = Path(args.data_out)
        data_out.parent.mkdir(parents=True, exist_ok=True)
        data_out.write_text(data_json, encoding="utf-8")

    size_kb = out.stat().st_size / 1024
    print(f"已生成 {out}  ({size_kb / 1024:.1f} MB)")
    print(f"  模式: {'空壳（未载入数据）' if is_empty else '内嵌数据'}  "
          f"档案: {len(payload['rows'])}  资源种类: {len(payload['materials'])}  "
          f"星系类型: {len(payload['systems'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
