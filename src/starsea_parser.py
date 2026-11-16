#!/usr/bin/env python3
"""cosmic_starsea 解析器

解析 m0-slot.json（或已导出的 cosmic_starsea 子树）中的星海数据。
新版存档（format_version >= 30）的 payload 为 base64 + brotli 压缩载荷，
本解析器会自动展开；旧版明文存档同样兼容。

用法示例（在项目根目录）:
    python src/starsea_parser.py summary
    python src/starsea_parser.py list --kind planet --rarity wonder
    python src/starsea_parser.py list --min-strength 2 --limit 20 --json
    python src/starsea_parser.py show 7b347396        # 支持唯一前缀
    python src/starsea_parser.py show 7b347396 --json # 输出完整原始数据
    python src/starsea_parser.py slots
    python src/starsea_parser.py receipts
    python src/starsea_parser.py pity
    python src/starsea_parser.py export --output dist/cosmic_starsea.json
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "m0-slot.json"
DEFAULT_EXPORT = ROOT / "dist" / "cosmic_starsea.json"

RARITY_ORDER = {"common": 0, "uncommon": 1, "rare": 2, "wonder": 3}
KIND_ORDER = {"planet": 0, "star": 1, "system": 2}
RARITY_LABEL = {"common": "普通", "uncommon": "罕见", "rare": "稀有", "wonder": "奇迹"}
KIND_LABEL = {"planet": "行星", "star": "恒星", "system": "星系"}


def setup_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


SAVE_META_KEYS = (
    "format_version", "save_magic", "saved_at_utc", "rules_version", "scenario_id",
)


def expand_payload(data):
    """展开新版存档的压缩载荷（base64 + brotli），旧版明文存档原样返回。"""
    if not isinstance(data, dict):
        return data
    payload = data.get("payload")
    if not isinstance(payload, str):
        return data

    storage = data.get("storage") if isinstance(data.get("storage"), dict) else {}
    algorithm = str(storage.get("algorithm") or "").strip().lower()

    if algorithm.startswith("brotli"):
        try:
            import brotli
        except ImportError as exc:  # 标准库没有 brotli
            raise SystemExit(
                "新版存档使用 Brotli 压缩，请先安装依赖：pip install brotli"
            ) from exc
        raw = brotli.decompress(base64.b64decode(payload))
    elif algorithm in ("", "none", "raw", "base64", "identity"):
        raw = base64.b64decode(payload)
    else:
        raise SystemExit(f"不支持的存档压缩算法: {algorithm or '(未标注)'}")

    expanded_length = storage.get("expanded_length")
    if isinstance(expanded_length, int) and expanded_length != len(raw):
        print(
            f"警告: 展开长度不匹配（预期 {expanded_length}，实际 {len(raw)}）",
            file=sys.stderr,
        )
    return json.loads(raw)


def load_save(path: str | Path):
    """读取存档，返回 (展开后的数据, 外层存档元信息)。"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    meta = {}
    if isinstance(data, dict):
        meta = {k: data[k] for k in SAVE_META_KEYS if k in data}
        storage = data.get("storage")
        if isinstance(storage, dict):
            meta["storage"] = {
                k: storage[k] for k in (
                    "version", "payload_format_version", "algorithm",
                    "expanded_length", "compressed_length", "summary",
                ) if k in storage
            }
    return expand_payload(data), meta


def load_json(path: str | Path):
    return load_save(path)[0]


class StarseaParser:
    """对 cosmic_starsea 子树的只读解析器。"""

    def __init__(self, save_path: str | Path):
        self.save_path = Path(save_path)
        self.raw, self.save_meta = load_save(self.save_path)
        self.starsea = self._extract_starsea(self.raw)
        self.artifacts: dict = self.starsea.get("artifacts") or {}

    @staticmethod
    def _extract_starsea(data) -> dict:
        if isinstance(data, dict):
            if isinstance(data.get("cosmic_starsea"), dict):
                return data["cosmic_starsea"]
            # 已导出的子树
            if "artifacts" in data and "slots" in data and "revision" in data:
                return data
            universe = data.get("universe")
            if isinstance(universe, dict) and isinstance(universe.get("cosmic_starsea"), dict):
                return universe["cosmic_starsea"]
        raise SystemExit(f"未在 {data!r} 中找到 cosmic_starsea")

    # ---------- 基础访问 ----------

    @staticmethod
    def _descriptor(defn: dict) -> dict:
        return defn.get("descriptor") or {}

    @staticmethod
    def _template(defn: dict) -> dict:
        return defn.get("template") or {}

    @staticmethod
    def _system(defn: dict) -> dict:
        return StarseaParser._template(defn).get("system") or {}

    @staticmethod
    def _worlds(defn: dict) -> list:
        return StarseaParser._template(defn).get("worlds") or []

    def iter_artifacts(self, *, kind=None, rarity=None, strength=None,
                       min_strength=None, max_strength=None, favorite=None,
                       origin=None, search=None):
        for aid, art in self.artifacts.items():
            defn = art.get("definition") or {}
            desc = self._descriptor(defn)
            s = desc.get("strength")
            if kind and defn.get("kind") != kind:
                continue
            if rarity and defn.get("rarity") != rarity:
                continue
            if strength is not None and s != strength:
                continue
            if min_strength is not None and (s is None or s < min_strength):
                continue
            if max_strength is not None and (s is None or s > max_strength):
                continue
            if favorite is not None and bool(art.get("favorite")) != favorite:
                continue
            if origin and art.get("origin") != origin:
                continue
            if search and not self._matches(aid, art, search):
                continue
            yield aid, art

    def _matches(self, aid: str, art: dict, needle: str) -> bool:
        needle = needle.lower()
        defn = art.get("definition") or {}
        texts = [aid, defn.get("kind", ""), defn.get("rarity", ""),
                 defn.get("system_kind_id", ""), defn.get("stellar_class", ""),
                 defn.get("planet_kind_id", "")]
        texts += [self._system(defn).get("label", ""), self._system(defn).get("id", "")]
        texts += [(w.get("label") or "") for w in self._worlds(defn)]
        texts += [(w.get("world_type") or "") for w in self._worlds(defn)]
        texts += [(w.get("environment_id") or "") for w in self._worlds(defn)]
        return any(needle in str(t).lower() for t in texts)

    def resolve_artifact(self, key: str) -> tuple[str, dict]:
        """按完整 id 或唯一前缀查找 artifact。"""
        key = key.strip().lower()
        if key in self.artifacts:
            return key, self.artifacts[key]
        matches = [aid for aid in self.artifacts if aid.lower().startswith(key)]
        if not matches:
            raise SystemExit(f"未找到 artifact: {key}")
        if len(matches) > 1:
            raise SystemExit(f"前缀 {key!r} 匹配到 {len(matches)} 条，请加长前缀: "
                             + ", ".join(m[:16] for m in matches[:8]))
        aid = matches[0]
        return aid, self.artifacts[aid]

    # ---------- 摘要 ----------

    def brief(self, aid: str, art: dict) -> dict:
        defn = art.get("definition") or {}
        desc = self._descriptor(defn)
        system = self._system(defn)
        worlds = self._worlds(defn)
        return {
            "id": aid,
            "kind": defn.get("kind"),
            "rarity": defn.get("rarity"),
            "strength": desc.get("strength"),
            "seed": desc.get("seed"),
            "generator_version": desc.get("generator_version"),
            "system_kind_id": defn.get("system_kind_id"),
            "stellar_class": defn.get("stellar_class"),
            "planet_kind_id": defn.get("planet_kind_id"),
            "body_count": defn.get("body_count"),
            "world_count": len(worlds),
            "system_label": system.get("label"),
            "world_labels": [w.get("label") for w in worlds],
            "origin": art.get("origin"),
            "favorite": bool(art.get("favorite")),
            "created_sequence": art.get("created_sequence"),
            "created_at_step": art.get("created_at_step"),
        }

    def summary(self) -> dict:
        cs = self.starsea
        arts = list(self.artifacts.values())
        kinds = Counter((a.get("definition") or {}).get("kind") for a in arts)
        rarities = Counter((a.get("definition") or {}).get("rarity") for a in arts)
        strengths = Counter(self._descriptor(a.get("definition") or {}).get("strength") for a in arts)
        origins = Counter(a.get("origin") for a in arts)
        favorites = sum(1 for a in arts if a.get("favorite"))
        body_counts = Counter((a.get("definition") or {}).get("body_count") for a in arts)
        world_counts = Counter(len(self._worlds(a.get("definition") or {})) for a in arts)

        slots = {}
        for name, slot in (cs.get("slots") or {}).items():
            defn = slot.get("definition") or {}
            slots[name] = {
                "instance_id": slot.get("instance_id"),
                "kind": defn.get("kind"),
                "rarity": defn.get("rarity"),
                "strength": self._descriptor(defn).get("strength"),
                "body_count": defn.get("body_count"),
            }

        return {
            "source": str(self.save_path),
            "save": self.save_meta,
            "version": cs.get("version"),
            "revision": cs.get("revision"),
            "next_bang_sequence": cs.get("next_bang_sequence"),
            "next_placement_sequence": cs.get("next_placement_sequence"),
            "artifact_count": len(arts),
            "kinds": dict(kinds),
            "rarities": dict(rarities),
            "strengths": dict(strengths),
            "origins": dict(origins),
            "favorites": favorites,
            "body_counts": dict(body_counts),
            "world_counts": dict(world_counts),
            "bang_receipts": len(cs.get("bang_receipts") or {}),
            "placement_receipts": len(cs.get("placement_receipts") or {}),
            "slots": slots,
            "pity": cs.get("pity") or {},
            "retired_world_ids": cs.get("retired_world_ids") or [],
            "retired_stellar_host_ids": cs.get("retired_stellar_host_ids") or [],
            "pending_adoptions": len(cs.get("pending_adoptions") or []),
        }

    # ---------- 输出 ----------

    def print_summary(self) -> None:
        s = self.summary()
        total = s["artifact_count"] or 1
        print(f"文件: {s['source']}")
        save = s.get("save") or {}
        if save:
            print(f"存档: format_version={save.get('format_version')} "
                  f"magic={save.get('save_magic')} scenario={save.get('scenario_id')} "
                  f"rules={save.get('rules_version')} saved_at={save.get('saved_at_utc')}")
            storage = save.get("storage") or {}
            if storage:
                print(f"存储: algorithm={storage.get('algorithm')} "
                      f"payload_format={storage.get('payload_format_version')} "
                      f"expanded={storage.get('expanded_length')} compressed={storage.get('compressed_length')}")
        print(f"cosmic_starsea: version={s['version']} revision={s['revision']}")
        print(f"计数: next_bang_sequence={s['next_bang_sequence']} "
              f"next_placement_sequence={s['next_placement_sequence']}")
        print(f"\nArtifacts: {s['artifact_count']}")
        print("  类型:")
        for k, v in sorted(s["kinds"].items(), key=lambda kv: -kv[1]):
            print(f"    {k:<8} {KIND_LABEL.get(k, ''):<4} {v:>6}  ({v / total:6.2%})")
        print("  稀有度:")
        for k, v in sorted(s["rarities"].items(), key=lambda kv: -kv[1]):
            print(f"    {k:<8} {RARITY_LABEL.get(k, ''):<4} {v:>6}  ({v / total:6.2%})")
        print("  强度:", ", ".join(f"{k}: {v}" for k, v in sorted(s["strengths"].items(), key=lambda kv: (kv[0] is None, kv[0]))))
        print("  来源:", ", ".join(f"{k}: {v}" for k, v in s["origins"].items()))
        print(f"  收藏: {s['favorites']}")
        print("  body_count 分布:", ", ".join(f"{k}: {v}" for k, v in sorted(s["body_counts"].items(), key=lambda kv: (kv[0] is None, kv[0]))))
        print("  实际天体数分布:", ", ".join(f"{k}: {v}" for k, v in sorted(s["world_counts"].items(), key=lambda kv: (kv[0] is None, kv[0]))))

        print(f"\n槽位: {len(s['slots'])}")
        for name, info in s["slots"].items():
            print(f"  [{name}] instance={info['instance_id']} "
                  f"kind={info['kind']} rarity={info['rarity']} strength={info['strength']} body_count={info['body_count']}")

        print(f"\n回执: bang={s['bang_receipts']} placement={s['placement_receipts']}")
        print(f"保底(pity): {json.dumps(s['pity'], ensure_ascii=False)}")
        print(f"退役世界: {len(s['retired_world_ids'])}")
        for wid in s["retired_world_ids"]:
            print(f"  - {wid}")
        if s["retired_stellar_host_ids"]:
            print(f"退役恒星宿主: {len(s['retired_stellar_host_ids'])}")
        print(f"待收养(pending_adoptions): {s['pending_adoptions']}")

    @staticmethod
    def print_brief_row(n: int, b: dict, full_id: bool = False) -> None:
        aid = b["id"] if full_id else b["id"][:12]
        world = ",".join([w for w in (b["world_labels"] or []) if w]) or "-"
        print(f"{n:>5}  seq={b['created_sequence']:<5} "
              f"{str(b['kind']):<7} {str(b['rarity']):<8} s={b['strength']}  "
              f"{str(b['system_kind_id']):<18} {str(b['planet_kind_id']):<16} "
              f"worlds={b['world_count']}  step={b['created_at_step']}  {aid}  {world}")

    def print_show(self, aid: str, art: dict) -> None:
        b = self.brief(aid, art)
        defn = art.get("definition") or {}
        desc = self._descriptor(defn)
        template = self._template(defn)
        system = self._system(defn)
        worlds = self._worlds(defn)

        print(f"Artifact {aid}")
        print(f"  kind={b['kind']} ({KIND_LABEL.get(b['kind'], '')})  "
              f"rarity={b['rarity']} ({RARITY_LABEL.get(b['rarity'], '')})  strength={b['strength']}")
        print(f"  origin={b['origin']}  favorite={b['favorite']}  "
              f"created_sequence={b['created_sequence']}  created_at_step={b['created_at_step']}")
        print(f"  content_hash={defn.get('content_hash')}")
        print(f"  descriptor: seed={desc.get('seed')} strength={desc.get('strength')} "
              f"generator_version={desc.get('generator_version')}")
        print(f"  system_kind={b['system_kind_id']}  stellar_class={b['stellar_class']}  "
              f"planet_kind={b['planet_kind_id']}  body_count={b['body_count']}  "
              f"worlds={b['world_count']}")
        print(f"  template: sequence={template.get('sequence')} "
              f"generation_version={template.get('generation_version')} "
              f"observation_index={template.get('observation_index')} "
              f"observation_space_version={template.get('observation_space_version')}")
        print(f"  system: {system.get('label')} (id={system.get('id')}) "
              f"{system.get('stellar_class')} distance={system.get('distance_milli_light_years')} mly "
              f"discovered={system.get('starting_discovered')} reachable={system.get('starting_reachable')}")

        print(f"  worlds[{len(worlds)}]:")
        for i, w in enumerate(worlds):
            cond = w.get("conditions") or {}
            ext = cond.get("extraction") or {}
            print(f"    [{i}] {w.get('label')}  {w.get('world_type')}  "
                  f"env={w.get('environment_id')}  naturally_habitable={w.get('naturally_habitable')}")
            print(f"        body_kind={cond.get('body_kind')} site={cond.get('site_kind')} "
                  f"habitation={cond.get('habitation_kind')} orbit={cond.get('orbit_index')} "
                  f"canvas={cond.get('canvas_kind')} size_bps={cond.get('size_bps')}")
            print(f"        mining_primary={cond.get('mining_primary_item')} "
                  f"per_material_bps={ext.get('per_material_bps')} "
                  f"abundance_bps={ext.get('abundance_bps')}")
            nodes = w.get("resource_nodes")
            if nodes:
                print(f"        resource_nodes[{len(nodes)}]: " + ", ".join(
                    f"{n.get('archetype_id')}@({(n.get('position') or {}).get('x')},{(n.get('position') or {}).get('y')})"
                    for n in nodes))

        frozen = template.get("frozen_worlds") or []
        print(f"  frozen_worlds: {len(frozen)}")

    def print_slots(self) -> None:
        slots = self.starsea.get("slots") or {}
        print(f"slots: {len(slots)}")
        for name, slot in slots.items():
            defn = slot.get("definition") or {}
            desc = self._descriptor(defn)
            system = self._system(defn)
            worlds = self._worlds(defn)
            print(f"\n[{name}]")
            print(f"  instance_id: {slot.get('instance_id')}")
            print(f"  kind={defn.get('kind')} rarity={defn.get('rarity')} "
                  f"strength={desc.get('strength')} body_count={defn.get('body_count')}")
            print(f"  system_kind={defn.get('system_kind_id')} stellar_class={defn.get('stellar_class')} "
                  f"planet_kind={defn.get('planet_kind_id')}")
            print(f"  descriptor.seed: {desc.get('seed')}")
            print(f"  system: {system.get('label')} (id={system.get('id')})")
            print(f"  worlds: {', '.join(str(w.get('label')) for w in worlds) or '-'}")

    def print_receipts(self) -> None:
        cs = self.starsea
        bang = cs.get("bang_receipts") or {}
        placement = cs.get("placement_receipts") or {}
        total_paid = 0
        pity_counts = Counter()
        for r in bang.values():
            try:
                total_paid += int(r.get("paid_milli") or 0)
            except (TypeError, ValueError):
                pass
            for flag in ("system_pity_applied", "rare_pity_applied", "wonder_pity_applied"):
                if r.get(flag):
                    pity_counts[flag] += 1
        print(f"bang_receipts: {len(bang)}  total_paid={total_paid / 1000:,.3f} (paid_milli={total_paid:,})")
        for flag, n in pity_counts.items():
            print(f"  {flag}: {n}")
        if bang:
            seqs = [r.get("sequence") for r in bang.values() if isinstance(r.get("sequence"), int)]
            if seqs:
                print(f"  sequence range: {min(seqs)}..{max(seqs)}")

        print(f"\nplacement_receipts: {len(placement)}")
        for op, r in placement.items():
            destroyed = r.get("destroyed") or []
            by_kind = Counter(d.get("kind") for d in destroyed)
            print(f"  {op[:12]}...  slot={r.get('slot')} revision={r.get('revision')} "
                  f"instance={r.get('instance_id')} destroyed={len(destroyed)} "
                  f"({', '.join(f'{k}:{v}' for k, v in by_kind.items()) or '-'})")

    def print_pity(self) -> None:
        pity = self.starsea.get("pity") or {}
        if not pity:
            print("pity: 空")
            return
        print("pity:")
        for key, val in pity.items():
            print(f"  [{key}] " + "  ".join(f"{k}={v}" for k, v in val.items()))

    def export(self, output: str | Path, pretty: bool = False) -> None:
        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(self.starsea, f, ensure_ascii=False, indent=2)
            else:
                json.dump(self.starsea, f, ensure_ascii=False, separators=(",", ":"))
        print(f"已导出 {len(self.artifacts)} 个 artifacts -> {out} "
              f"({out.stat().st_size / 1048576:.1f} MB)")

    def export_csv(self, output: str | Path, rows) -> None:
        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        fields = ["id", "kind", "rarity", "strength", "seed", "generator_version",
                  "system_kind_id", "stellar_class", "planet_kind_id", "body_count",
                  "world_count", "system_label", "world_labels", "origin", "favorite",
                  "created_sequence", "created_at_step"]
        with open(out, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for b in rows:
                row = dict(b)
                row["world_labels"] = "|".join(str(x) for x in (b["world_labels"] or []))
                writer.writerow(row)
        print(f"已写入 {out} ({len(rows)} 行)")


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="解析存档中的 cosmic_starsea（星海）数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("-i", "--input", default=str(DEFAULT_INPUT),
                   help=f"存档文件或已导出的 cosmic_starsea JSON（默认 {DEFAULT_INPUT.relative_to(ROOT)}）")
    sub = p.add_subparsers(dest="command")

    sp = sub.add_parser("summary", help="总体统计（默认）")
    sp.add_argument("--json", action="store_true", help="输出 JSON")

    sp = sub.add_parser("list", help="列出 artifacts，支持筛选")
    sp.add_argument("--kind", choices=sorted(KIND_ORDER), help="planet/star/system")
    sp.add_argument("--rarity", choices=sorted(RARITY_ORDER), help="common/uncommon/rare/wonder")
    sp.add_argument("--strength", type=int, help="精确强度")
    sp.add_argument("--min-strength", type=int, help="最小强度")
    sp.add_argument("--max-strength", type=int, help="最大强度")
    sp.add_argument("--favorite", action="store_true", help="只看收藏")
    sp.add_argument("--origin", help="按来源筛选，如 self")
    sp.add_argument("--search", help="在 id/系统名/世界名/类型等字段中搜索")
    sp.add_argument("--sort", choices=["sequence", "step", "strength", "rarity", "kind"],
                    default="sequence", help="排序字段（默认 sequence）")
    sp.add_argument("--desc", action="store_true", help="降序")
    sp.add_argument("--limit", type=int, default=50, help="最多显示条数，0 表示全部（默认 50）")
    sp.add_argument("--full-id", action="store_true", help="显示完整 id")
    sp.add_argument("--json", action="store_true", help="输出 JSON")
    sp.add_argument("--csv", metavar="FILE", help="导出筛选结果为 CSV")

    sp = sub.add_parser("show", help="查看单个 artifact 详情（支持唯一 id 前缀）")
    sp.add_argument("artifact", help="完整 id 或唯一前缀")
    sp.add_argument("--json", action="store_true", help="输出完整原始 JSON")

    sp = sub.add_parser("slots", help="查看当前槽位")
    sp.add_argument("--json", action="store_true", help="输出原始 JSON")

    sp = sub.add_parser("receipts", help="查看抽取/放置回执")
    sp.add_argument("--json", action="store_true", help="输出原始 JSON")

    sp = sub.add_parser("pity", help="查看保底计数")
    sp.add_argument("--json", action="store_true", help="输出原始 JSON")

    sp = sub.add_parser("export", help="导出 cosmic_starsea 子树为独立 JSON")
    sp.add_argument("--output", "-o", default=str(DEFAULT_EXPORT),
                    help=f"输出文件（默认 {DEFAULT_EXPORT.relative_to(ROOT)}）")
    sp.add_argument("--pretty", action="store_true", help="缩进格式化（文件更大）")

    return p


def main(argv=None) -> int:
    setup_stdout()
    args = build_argparser().parse_args(argv)
    parser = StarseaParser(args.input)
    cmd = args.command or "summary"

    if cmd == "summary":
        if args.json:
            print(json.dumps(parser.summary(), ensure_ascii=False, indent=2))
        else:
            parser.print_summary()
        return 0

    if cmd == "list":
        rows = list(parser.iter_artifacts(
            kind=args.kind, rarity=args.rarity, strength=args.strength,
            min_strength=args.min_strength, max_strength=args.max_strength,
            favorite=True if args.favorite else None, origin=args.origin,
            search=args.search,
        ))
        sort_key = {
            "sequence": lambda x: x[1].get("created_sequence") or 0,
            "step": lambda x: x[1].get("created_at_step") or 0,
            "strength": lambda x: parser._descriptor(x[1].get("definition") or {}).get("strength") or 0,
            "rarity": lambda x: RARITY_ORDER.get((x[1].get("definition") or {}).get("rarity"), -1),
            "kind": lambda x: KIND_ORDER.get((x[1].get("definition") or {}).get("kind"), -1),
        }[args.sort]
        rows.sort(key=sort_key, reverse=args.desc)
        briefs = [parser.brief(aid, art) for aid, art in rows]

        if args.csv:
            parser.export_csv(args.csv, briefs)
            return 0
        if args.json:
            shown = briefs if args.limit == 0 else briefs[:args.limit]
            print(json.dumps({"total": len(briefs), "items": shown}, ensure_ascii=False, indent=2))
            return 0
        print(f"共 {len(briefs)} 条" + (f"，显示前 {min(args.limit, len(briefs))} 条" if args.limit else ""))
        for n, b in enumerate(briefs if args.limit == 0 else briefs[:args.limit], 1):
            parser.print_brief_row(n, b, full_id=args.full_id)
        return 0

    if cmd == "show":
        aid, art = parser.resolve_artifact(args.artifact)
        if args.json:
            print(json.dumps(art, ensure_ascii=False, indent=2))
        else:
            parser.print_show(aid, art)
        return 0

    if cmd == "slots":
        if args.json:
            print(json.dumps(parser.starsea.get("slots") or {}, ensure_ascii=False, indent=2))
        else:
            parser.print_slots()
        return 0

    if cmd == "receipts":
        if args.json:
            payload = {
                "bang_receipts": parser.starsea.get("bang_receipts") or {},
                "placement_receipts": parser.starsea.get("placement_receipts") or {},
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            parser.print_receipts()
        return 0

    if cmd == "pity":
        if args.json:
            print(json.dumps(parser.starsea.get("pity") or {}, ensure_ascii=False, indent=2))
        else:
            parser.print_pity()
        return 0

    if cmd == "export":
        parser.export(args.output, pretty=args.pretty)
        return 0

    raise SystemExit(f"未知命令: {cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
