# 星海（cosmic_starsea）存档解析与可视化

从游戏存档中提取 `universe.cosmic_starsea`，解析星海档案与天体数据，并生成一个完全离线、可筛选排序的中文交互式 HTML 仪表盘。

当前数据：**11,404 个档案 / 12,546 个本体天体 / 20 种资源**，支持新版 brotli 压缩存档与旧版明文存档。

**在线页面**：<https://gyxqq.github.io/starsea-dashboard/>

页面是默认空壳（不含存档数据），打开后通过「载入 JSON」加载自己的存档；`docs/index.html` 由 `dist/starsea_dashboard.html` 复制而来。如需发布内嵌数据版，把 `dist/starsea_dashboard_data.html` 复制为 `docs/index.html` 后提交即可。

---

## 目录

1. [快速开始](#快速开始)
2. [文件结构](#文件结构)
3. [分析过程](#分析过程)
4. [存档结构](#存档结构)
5. [数据模型](#数据模型)
6. [指标定义](#指标定义)
7. [解析器](#解析器)
8. [仪表盘](#仪表盘)
9. [当前数据概览](#当前数据概览)
10. [版本迁移记录](#版本迁移记录)
11. [验证记录](#验证记录)
12. [已知限制与后续方向](#已知限制与后续方向)

---

## 快速开始

### 环境

- Python 3.11+
- 第三方依赖仅 `brotli`（CLI / 构建时解压新版存档用；浏览器端解码器已内置于 HTML）

```bash
pip install brotli
```

### 常用命令

```bash
# 1. 总览存档（默认读取 data/m0-slot.json）
python src/starsea_parser.py summary

# 2. 查看 / 筛选档案
python src/starsea_parser.py list --kind star --rarity wonder --limit 20
python src/starsea_parser.py show 7b347396            # 支持唯一 id 前缀

# 3. 导出 cosmic_starsea 子树（供网页版“载入 JSON”使用）
python src/starsea_parser.py export --output dist/cosmic_starsea.json

# 4. 构建空壳（不含数据，默认输出 dist/starsea_dashboard.html）
python src/build_starsea_dashboard.py

# 5. 构建内嵌数据的仪表盘（默认输出 dist/starsea_dashboard_data.html）
python src/build_starsea_dashboard.py -i data/m0-slot.json
```

- `dist/starsea_dashboard.html`：空壳，约 0.4 MB（内含 Brotli WASM 解码器），打开后通过右上角“载入 JSON”加载存档
- `dist/starsea_dashboard_data.html`：内嵌数据，约 11 MB，双击即可离线使用

两者都无需服务器。

### Makefile（可选）

项目根目录提供 `Makefile`，需要 GNU Make（Windows 可先 `winget install ezwinports.make` 或 `choco install make`）：

```bash
make build          # 空壳 + 数据版
make build-shell    # 只构建空壳
make build-data     # 只构建数据版
make pages          # 用空壳更新 docs/index.html
make pages-data     # 用数据版更新 docs/index.html
make publish        # 空壳更新并 push 到 GitHub Pages
make publish-data   # 数据版更新并 push
make parser         # 存档 summary
make serve          # 本地预览 docs（http://localhost:8000）
make clean          # 清理构建产物
```

可通过变量覆盖默认值：`make build-data INPUT=other.json PYTHON=py`。

---

## 文件结构

```
starsea-dashboard/
├── src/                        # 源码
│   ├── starsea_parser.py       # 存档解码、cosmic_starsea 解析器与 CLI
│   ├── build_starsea_dashboard.py
│   ├── templates/
│   │   └── dashboard_template.html  # 仪表盘模板（HTML/CSS/JS）
│   └── vendor/
│       └── brotli-dec-wasm/    # 浏览器端 Brotli WASM 解码器
├── data/                       # 输入数据（游戏存档，默认不进 git）
│   └── m0-slot.json
├── dist/                       # 构建产物（默认不进 git）
│   ├── starsea_dashboard.html       # 空壳（无数据，可在网页里载入 JSON）
│   └── starsea_dashboard_data.html  # 内嵌数据的单文件离线仪表盘
├── .gitignore
└── README.md
```

| 路径 | 大小 | 作用 |
|---|---:|---|
| `src/starsea_parser.py` | ~27 KB | 存档解码、`cosmic_starsea` 解析器与 CLI |
| `src/build_starsea_dashboard.py` | ~9 KB | 把解析结果压缩成仪表盘 payload，注入模板 |
| `src/templates/dashboard_template.html` | ~86 KB | 仪表盘模板（HTML/CSS/JS，数据占位符） |
| `src/vendor/brotli-dec-wasm/` | ~220 KB | 浏览器端 Brotli WASM 解码器（构建时内嵌） |
| `dist/starsea_dashboard.html` | ~0.4 MB | 空壳仪表盘，通过“载入 JSON”读取存档 |
| `dist/starsea_dashboard_data.html` | ~11 MB | 内嵌当前数据、可直接分发的单文件仪表盘 |
| `data/m0-slot.json` | ~9.6 MB | 当前游戏存档（v31，brotli 压缩载荷） |

运行时会生成 `__pycache__/`；`export` 会在 `dist/` 产生较大的子树 JSON，均可按需删除。

---

## 分析过程

### 1. 在 158 MB 单行 JSON 中定位“星海”

最初的存档是约 **158,012,295 字节**的单行 JSON，直接文本搜索 `星海` **没有结果**——存档内部使用的是英文键名，本地化文本不落盘。

随后改用单字搜索 `星` / `海`，在约 **53,286,632 字节**处发现 `starsea`，确认目标路径为：

```
universe.cosmic_starsea
```

这一步遇到的坑：

- 文件只有一行，正则回溯容易让 `grep -r` 超时或被放到后台；
- 最终使用 `grep -bo` 先拿字节偏移，再用 `dd` 截取该偏移附近的片段确认上下文；
- Windows 终端默认 cp936，输出中文会乱码，Python 侧统一设置 `PYTHONIOENCODING=utf-8` 并在脚本里 `sys.stdout.reconfigure(encoding="utf-8")`。

确认 `cosmic_starsea` 下包含：

```
version, revision, next_bang_sequence, next_placement_sequence,
artifacts, pity, bang_receipts, slots, placement_receipts,
pending_adoptions, retired_world_ids, retired_stellar_host_ids
```

于是确定解析对象不是 `universe.worlds`、`star_systems` 这些运行时世界，而是“星海抽取档案”这一层。

### 2. 初版存档（format_version 25）

初版可直接 `json.load`：

- 文件：158,012,295 字节，单行明文 JSON
- `save_magic = ICF-M0-DEV`
- `format_version = 25`
- `cosmic_starsea.revision = 9,906`
- `artifacts = 9,902`

据此完成了第一版解析器、统计命令和仪表盘。

### 3. 新版存档（format_version 31）

游戏更新后，同一路径的 `m0-slot.json` 变成 **9,644,131 字节**，直接读取顶层已经找不到 `universe`：

```
format_version, save_magic, saved_at_utc, rules_version,
scenario_id, storage, payload, checksum_sha256
```

`payload` 是一个约 964 万字符的字符串，`storage` 描述了编码方式：

| 字段 | 值 |
|---|---|
| `storage.version` | 2 |
| `storage.payload_format_version` | 42 |
| `storage.algorithm` | `brotli-q4-v1` |
| `storage.compressed_length` | 7,232,241 |
| `storage.expanded_length` | 227,022,957 |

解码流程：

```python
import base64, brotli, json

wrapper = json.load(open("m0-slot.json", encoding="utf-8"))
raw = brotli.decompress(base64.b64decode(wrapper["payload"]))
save = json.loads(raw)          # 227 MB 的 JSON
cs = save["universe"]["cosmic_starsea"]
```

展开后内层 `format_version = 42`，`rules_version = 0.1.0+copper-magma-r1`，`scenario_id = civilization-ark-sandbox`。

新版之所以从 158 MB 缩到 9.6 MB，是因为整个 227 MB 的 JSON 被 brotli 压缩后再 base64 封装；解析端需要先解压，**不能直接 `json.load` 顶层**。

### 4. 数据语义变化

新版生成器（`generation_version = 5`）带来两个需要注意的变化：

#### 4.1 恒星档案的本体只有恒星

旧版中 `definition.body_count == len(template.worlds)`；新版中恒星档案的 `body_count` 固定为 1（恒星本体），而 `worlds` 可能有 2–4 个天体。经游戏内核对，这些 `worlds` 是档案生成星系的预览天体，**不是档案本体**：

| body_count | template.worlds | 档案数 | 含义 |
|---:|---:|---:|---|
| 1 | 1 | 9,166 | 行星档案 1 个天体 / 星系档案 1 个天体 |
| 1 | 2 | 643 | 恒星档案：1 颗恒星本体 + 2 个星系预览天体 |
| 1 | 3 | 605 | 恒星档案：1 颗恒星本体 + 3 个星系预览天体 |
| 1 | 4 | 486 | 恒星档案：1 颗恒星本体 + 4 个星系预览天体 |
| 2–7 | 2–7 | 504 | 星系档案：每个 world 都是档案本体 |

因此：

- **行星 / 星系档案**：`body = len(worlds)`，每个 world 都是一个天体。
- **恒星档案**：`body = definition.body_count`（= 1，恒星本体），`template.worlds` 只作为星系预览保留在详情抽屉中，不计入档案天体数，也不参与档案级规模/资源聚合。
- 解析器仍同时保留原始 `body_count` 和 `world_count`，便于对照。

例子：恒星档案 `fcb41a3a1dfd…`（创建序列 11,404），白矮星，`body_count = 1`；`worlds` 里另有 3 个预览天体（黑洞 + 2 个无气小天体），在仪表盘详情中显示为“星系天体（预览）”。

#### 4.2 强度出现 6 和 7

旧数据最高强度为 6；新数据分布为：

```
1: 9501, 2: 1800, 3: 100, 6: 2, 7: 1
```

仪表盘强度筛选因此改为从数据动态生成（当前 1–7），不再硬编码 1–6。

#### 4.3 新增但不影响现有统计的字段

- `template.frozen_worlds`：部署快照格式（`{world, resource_nodes}`），不是活动世界
- `system.starting_discovered` / `system.starting_reachable`
- `template.sequence` / `observation_index` / `observation_space_version`

### 5. 从“档案表”到“天体表”

表格按**档案本体**展示，每个档案一行，三种档案类型各自呈现：

- 行星档案：显示行星本体一行，规模/采矿/人口/宜居/资源取该天体的数据
- 恒星档案：显示恒星本体一行，天体类型列显示恒星分类（如“白矮星”）；`template.worlds` 的 2–4 个星系预览天体只在详情抽屉中显示
- 星系档案：显示星系本体一行，天体类型为“星系”；列中的规模/采矿/人口/资源取星系内含天体的聚合值，不再把每个恒星/行星拆成多行；资源展开面板显示星系内全部资源的合计

表格身份列使用短档案 id（12 位），完整 id 放在单元格 `title` 与详情抽屉中。

### 6. 交互迭代

在可视化过程中逐步修正的问题：

- **初始资源列直接铺满** → 改为“N 种资源 ▾”下拉，默认收起，点击展开数值与细条
- **所有分类塞在一个搜索框** → 拆成“搜索范围”下拉 + 独立筛选下拉
- **行星类型/星系类型混在一起** → 拆成“档案类型 / 天体类型 / 星系类型”三个维度
- **创建序列无法搜索** → 搜索范围新增“创建序列”，并纳入“全部字段”
- **每个世界的宜居度错误**：早期实现复用了运行中的最大值，改为读取各自的 `habitability_bps`
- **对数轴混用“亿/万亿”单位**：改为 `10⁸`、`10¹³` 等上标刻度
- **散点轴出现负数刻度**：百分比留白导致的负刻度，改为非负数据时下限钳制到 0
- **抽屉关闭按钮被挤成两行**：设置 `flex: 0 0 auto; white-space: nowrap`
- **切换存档后筛选器不刷新**：拆分 `resetState()` 与 `refreshOptions()`，载入后重建所有选项与坐标域

---

## 存档结构

### 新版外层（format_version 31）

```json
{
  "format_version": 31,
  "save_magic": "ICF-M0-DEV",
  "saved_at_utc": "2026-11-16T03:16:53.7445962+00:00",
  "rules_version": "0.1.0+copper-magma-r1",
  "scenario_id": "civilization-ark-sandbox",
  "storage": {
    "version": 2,
    "payload_format_version": 42,
    "algorithm": "brotli-q4-v1",
    "expanded_length": 227022957,
    "compressed_length": 7232241
  },
  "payload": "<base64(brotli(json))>",
  "checksum_sha256": "..."
}
```

### 展开后的 `cosmic_starsea`

| 字段 | 类型 | 当前值 / 含义 |
|---|---|---:|
| `version` | int | 1 |
| `revision` | int | 11,409 |
| `next_bang_sequence` | int | 11,405 |
| `next_placement_sequence` | int | 5 |
| `artifacts` | dict | 11,404，键为 64 位十六进制 id |
| `pity` | dict | 按强度记录保底计数 |
| `bang_receipts` | dict | 11,404 条抽取回执 |
| `slots` | dict | 2 个已放置槽位 |
| `placement_receipts` | dict | 5 条放置回执 |
| `pending_adoptions` | list | 0 |
| `retired_world_ids` | list | 3 |
| `retired_stellar_host_ids` | list | 0 |

---

## 数据模型

每个 artifact 的核心结构：

```json
{
  "id": "7b3473969c024ce6cc0feb2e8dbffc43...",
  "definition": {
    "descriptor": {
      "seed": "e74a88a9936cd71a...",
      "strength": 1,
      "generator_version": 2
    },
    "kind": "planet",
    "rarity": "uncommon",
    "content_hash": "...",
    "body_count": 1,
    "system_kind_id": "habitable_belt",
    "stellar_class": "K-class",
    "planet_kind_id": "ocean_world",
    "template": {
      "system": {
        "id": "frontier-grid2-00000001",
        "label": "曦湾 / Dawn Bay",
        "stellar_class": "K-class",
        "distance_milli_light_years": 4932,
        "starting_discovered": true,
        "starting_reachable": false
      },
      "worlds": [
        {
          "label": "S000001-P01",
          "world_type": "ocean_world",
          "environment_id": "ocean_surface",
          "naturally_habitable": false,
          "conditions": {
            "body_kind": "planet",
            "site_kind": "ocean_platform",
            "canvas_kind": "platform",
            "orbit_index": 1,
            "size_bps": 40000,
            "habitability_bps": 4000,
            "natural_population_capacity": 110,
            "solar_output_bps": 7985,
            "wind_output_bps": 14163,
            "stellar_capacity_kw": 4134922671,
            "mining_primary_item": "pelagic_mineral_slurry",
            "extraction": {
              "per_material_bps": {"pelagic_mineral_slurry": 40000},
              "abundance_bps": {"pelagic_mineral_slurry": 10000}
            }
          }
        }
      ]
    }
  },
  "origin": "self",
  "favorite": false,
  "created_sequence": 1,
  "created_at_step": 1348372
}
```

### 字段速查

| 路径 | 说明 |
|---|---|
| `definition.kind` | `planet` / `star` / `system` |
| `definition.rarity` | `common` / `uncommon` / `rare` / `wonder` |
| `definition.descriptor.strength` | 1–7，当前数据实际出现 1,2,3,6,7 |
| `definition.body_count` | 档案本体天体数；恒星档案恒为 1（恒星本体） |
| `definition.template.worlds[]` | 天体贴，1–7 个；恒星档案中为星系预览天体，不算档案本体 |
| `worlds[].world_type` | 12 种世界类型 |
| `worlds[].conditions.body_kind` | `planet` / `gas_giant` / `minor_body` / `nebula` / `neutron_star` / `black_hole` / `artificial_structure` |
| `worlds[].conditions.extraction.per_material_bps` | 每种材料的采矿速率 |
| `worlds[].conditions.size_bps` | 天体规模 |
| `worlds[].conditions.habitability_bps` | 宜居度 |
| `worlds[].conditions.natural_population_capacity` | 人口上限 |
| `system.distance_milli_light_years` | 距离，单位毫光年 |
| `created_sequence` | 创建序列，抽取顺序 |
| `created_at_step` | 创建时的游戏步数 |

---

## 指标定义

### 档案级（聚合）

| 指标 | 计算方式 |
|---|---|
| `body` | 行星/星系档案为 `len(template.worlds)`；恒星档案为 `definition.body_count`（= 1，恒星本体） |
| `size` | 所有世界 `size_bps` 之和；界面显示时除以 10000 并加 `x` |
| `sizeMax` | 所有世界 `size_bps` 最大值 |
| `mine` | 所有世界 `per_material_bps` 所有值之和 |
| `pops` | 所有世界 `natural_population_capacity` 之和 |
| `solar` | 所有世界 `solar_output_bps` 最大值 |
| `wind` | 所有世界 `wind_output_bps` 最大值 |
| `hab` | 所有世界 `habitability_bps` 最大值 |
| `cap` | 系统 `stellar_capacity_kw`；缺失时取世界最大值 |
| `dist` | 系统 `distance_milli_light_years` |
| `matCount` | 所有世界材料集合大小 |
| `mats` | 去重后的材料 key 列表 |

### 档案本体（表格每行）

| 指标 | 计算方式 |
|---|---|
| `size` | 该世界 `size_bps`；界面显示时除以 10000 并加 `x` |
| `mine` | 该世界所有材料 `per_material_bps` 之和 |
| `pop` | `natural_population_capacity` |
| `hab` | `habitability_bps` |
| `matCount` | 该世界材料种类数 |
| `mats` | 材料 → 速率映射 |
| `minePrimary` | `mining_primary_item` |

---

## 解析器

`starsea_parser.py` 只依赖标准库 + `brotli`，不引入 pandas 等重依赖。

### 解码与定位

```python
self.raw, self.save_meta = load_save(path)
self.starsea = self._extract_starsea(self.raw)
self.artifacts = self.starsea["artifacts"]
```

支持三种输入：

1. 新版完整存档（`payload` + `storage`，自动 base64 + brotli 展开）
2. 旧版完整存档（`universe.cosmic_starsea`）
3. `export` 导出的 `cosmic_starsea` 子树（含 `artifacts` / `slots` / `revision`）

### CLI

| 命令 | 说明 |
|---|---|
| `summary` | 存档格式、类型/稀有度/强度分布、槽位、回执、保底、退役世界 |
| `list` | 筛选与排序列表；支持 `--kind --rarity --strength --min/max-strength --favorite --origin --search --sort --desc --limit --json --csv` |
| `show ID` | 单个 artifact 详情，支持唯一前缀 |
| `slots` | 槽位内容 |
| `receipts` | 抽取/放置回执汇总 |
| `pity` | 保底计数 |
| `export` | 导出 `cosmic_starsea` 子树 |

示例：

```bash
python src/starsea_parser.py list --kind system --rarity wonder --limit 5
python src/starsea_parser.py list --min-strength 6 --sort strength --desc
python src/starsea_parser.py show 7b347396 --json
python src/starsea_parser.py export --output dist/cosmic_starsea.json
```

### 性能

- 新版存档解压后 227 MB，`json.loads` 与 artifact 遍历属于一次性操作；
- 11,404 个档案的构建在数秒内完成；
- `export` 导出的子树约 112 MB，浏览器载入前需留意内存。

---

## 仪表盘

### 构建流程

```
# 默认：空壳
src/templates/dashboard_template.html + 空 payload
   └─ dist/starsea_dashboard.html（约 0.4 MB，可在网页里载入 JSON）

# -i：内嵌数据
data/m0-slot.json
   ├─ universe.cosmic_starsea
   │    └─ build_rows()：每个 artifact 一行紧凑数据（含 worlds）
   │         └─ build_payload()：meta + materials + systems + rows
   └─ universe.world_seed / procedural_expansion / worlds
        └─ build_worlds()：385 个存档天体（worlds + worldMeta）
             └─ 一起注入 src/templates/dashboard_template.html 的 /*__STARSEA_DATA__*/
                  └─ dist/starsea_dashboard_data.html（单文件，约 11.5 MB）
```

注入时会转义 `</`、U+2028、U+2029，避免破坏 `<script>`。

### 页面结构

- 顶栏：标题、数据源、`星海档案 / 存档天体` 视图切换、`载入 JSON`、明暗主题切换
- Hero：匹配档案数 + 4 个 KPI（奇迹档案、稀有及以上、平均强度、资源种类）；存档天体视图下切换为已部署、星系数量、平均规模、资源种类
- 横向排列的筛选组：搜索、档案类型、稀有度、天体类型、资源、星系类型横向铺开，每组内部为纵向开关列表，并带独立“反选”按钮
- 第二行：强度、档案天体数、指标范围、重置
- 内容区：图表、档案表
- 详情抽屉

### 图表

| 图表 | 形式 | 说明 |
|---|---|---|
| 类型构成 | 横向条形 | 行星 / 恒星 / 星系档案数 |
| 稀有度构成 | 有序色阶条形 | 普通 → 罕见 → 稀有 → 奇迹 |
| 本体天体数分布 | 柱状 | 每个档案的本体天体数（恒星档案为 1，星系档案为内含天体数） |
| 规模（×10000） × 资源总量 | 散点 | 点色 = 档案类型，点大小随天体数；规模刻度显示为 `1x`、`2x` |
| 恒星能量 × 距离 | 散点（对数 Y） | 距离与恒星能量，刻度用 `10ⁿ` |
| 资源出现频次 | 横向条形 | 当前筛选下包含该资源的档案数 |

配色遵循数据可视化校验流程：

| 角色 | 浅色 | 深色 |
|---|---|---|
| 行星 | `#2a78d6` | `#3987e5` |
| 恒星 | `#eb6834` | `#d95926` |
| 星系 | `#1baf7a` | `#199e70` |
| 稀有度色阶 | `#86b6ef → #5598e7 → #2a78d6 → #1c5cab` | `#184f95 → #256abf → #3987e5 → #86b6ef` |

三个分类色在浅/深色下均通过全配对 CVD 校验；稀有度使用单色有序色阶。标记使用 2px 表面间隙与细线网格，避免重边框。

### 档案表

- 每个档案一行；身份列 = 短档案 id
- 行星档案显示行星本体；恒星档案显示恒星本体；星系档案显示整个星系（内含天体不拆行）
- 列：序、档案、档案类型、天体类型、稀有度、强度、星系类型、规模、采矿速率、人口上限、宜居度、资源
- 规模/采矿/人口/宜居/资源：行星取该天体，恒星显示“—”，星系取内含天体的聚合值
- 规模显示除以 10000 并加 `x`（10000 → `1x`，20000 → `2x`）；指标范围选“规模（x）”时，输入框提示“最小 x / 最大 x”，筛选值也按同一口径（输入 1–4 即 1x–4x）
- “指标范围”支持添加多条条件：每条包含指标、最小/最大、删除按钮；多条条件为“且”关系
- 资源列是下拉按钮：`N 种资源 ▾`，行星显示该天体资源，星系显示全部内含资源的合计
- 排序：点击表头，或使用表头工具栏的「排序」下拉选择字段，再用「升序 ▲ / 降序 ▼」切换方向；可选创建序列、步数、编号、类型、稀有度、强度、天体数、星系类型、恒星分类、天体类型、规模、采矿、人口、宜居、资源种类、恒星能量、距离、种子
- 独立的「资源排序」下拉：可按「碳、铜矿、冰、钛矿……」等单个资源排序（按该材料在档案/天体中的合计 bps；没有该材料记为 0）；选中资源时普通排序下拉会暂时禁用，清空后恢复
- 点击行打开档案详情
- 分页 25 / 50 / 100 / 200
- CSV 导出按当前筛选与排序导出全部档案

### 存档天体视图

顶栏切换到「存档天体」后，数据源从星海档案改为存档里的实际天体：

- 范围：`universe.world_seed.worlds`（19）+ `universe.procedural_expansion.systems[].frozen_worlds`（362）+ 4 个运行时独有天体 = **385 个天体 / 128 个星系**（当前 40 个已部署）
- 兼容旧版 `world_seed` 的扁平 `*_bps` 采矿字段；`mining_primary_item` 缺失时取最大材料
- 运行时独有天体会尽量从槽位 `materialized`、基础世界或 `world_notes` 补全名称/星系/资源；无法补全的显示 ID
- 筛选：天体类型、环境、星系类型、恒星分类、资源（均为开关多选 + 每组独立反选），部署状态、规模（x）、人口上限、宜居度范围
- KPI：已部署 / 星系数量 / 平均规模 / 资源种类
- 图表：天体类型、环境、部署状态、恒星分类、规模 × 采矿速率、资源出现频次
- 天体表：天体、类型、星系、恒星分类、环境、规模、采矿速率、人口上限、宜居度、资源、部署状态
- 排序：点击表头，或使用「排序」下拉 + 升序/降序按钮；可选名称、类型、星系、恒星分类、星系类型、环境、规模、采矿、人口、宜居、资源种类、部署、距离、轨道、运行时步数、来源、编号
- 独立的「资源排序」下拉：可按「碳、铜矿、冰……」等单个资源排序（按该材料在天体中的合计 bps；没有该材料记为 0）；选中资源时普通排序下拉会暂时禁用，清空后恢复
- 点击行打开天体详情；CSV 导出为 `存档天体_筛选结果.csv`

### 搜索与筛选

- **搜索范围**：全部字段 / 档案编号 / 创建序列 / 种子 / 星系名称 / 天体编号 / 资源
- **全部字段**包含 id、创建序列、创建步数、种子、星系名称、资源（中英文）、星系/行星/恒星类型、天体标签与类型
- 档案类型、稀有度、天体类型、资源、星系类型均为开关式多选：组内为“或”，组间为“且”；不勾选表示该组不限制
- 每组右上角有独立的“反选”按钮，只翻转该组选项；空数据组显示“暂无数据”并禁用反选
- 指标范围可点击“+ 添加指标”增加多条范围条件，所有已填写的范围同时生效（且关系）
- 所有筛选共同作用于图表与表格；恒星档案的星系预览天体不参与天体类型筛选
- 强度与天体数选项从当前数据动态生成

### 中文显示

内置枚举字典：

`KIND_LABEL`、`RARITY_LABEL`、`SYS_ZH`、`PLANET_ZH`、`STELLAR_ZH`、`BODY_ZH`、`SITE_ZH`、`CANVAS_ZH`、`ENV_ZH`、`WORLD_ZH`、`MATERIAL_ZH`

逻辑与筛选仍使用原始英文 key，仅在展示层翻译。

### 主题与本地状态

- 明/暗主题跟随系统，可手动切换并写入 `localStorage`
- 切换主题会重绘 Canvas 图表（取当前 CSS 变量）
- 窗口尺寸变化时防抖重绘

### 载入其他存档

网页版支持：

- `载入 JSON` 文件选择
- 拖放 `.json` 到页面
- 接受旧版完整存档或 `src/starsea_parser.py export` 导出的子树

**新版存档（`payload` + `storage`）是 base64 + brotli 压缩的 227 MB JSON**，不是可直接读取的明文。构建时会把 `brotli-dec-wasm`（约 204 KB WASM）内嵌进 HTML，页面按以下顺序解压：

1. 内置 WASM 解码器（Chrome / Firefox / Safari 通用，离线可用）
2. 浏览器原生 `DecompressionStream('brotli')`（较新的 Firefox / Safari）
3. 都不可用时给出提示，并建议用 CLI 导出

因此 Chrome 现在也能直接载入新版压缩存档。注意解压后是 227 MB JSON，解析会占用较多内存，低配机器建议用 CLI 生成数据版：

```bash
# 生成内嵌数据版（推荐）
python src/build_starsea_dashboard.py -i data/新存档.json -o dist/starsea_dashboard_data.html

# 或先导出子树，再在网页里载入
python src/starsea_parser.py export --output dist/cosmic_starsea.json
```

载入成功后会在浏览器内重新计算 rows、资源/星系选项、筛选器、坐标域和页脚。

---

## 当前数据概览

数据源：`m0-slot.json`（v31 / payload 42 / brotli），场景 `civilization-ark-sandbox`，规则 `0.1.0+copper-magma-r1`。

### 档案

| 维度 | 数量 |
|---|---:|
| 档案 | 11,404 |
| 档案本体天体 | 12,546 |
| 行星档案 | 8,860（77.69%） |
| 恒星档案 | 1,874（16.43%） |
| 星系档案 | 670（5.88%） |

### 存档天体

| 维度 | 数量 |
|---|---:|
| 存档天体 | 385 |
| 星系 | 128 |
| 已部署 | 40 |
| 未部署 | 345 |
| 天体类型 | 16 |
| 环境类型 | 14 |

### 稀有度与强度

| 稀有度 | 数量 |
|---|---:|
| 普通 common | 8,667 |
| 罕见 uncommon | 1,977 |
| 稀有 rare | 628 |
| 奇迹 wonder | 132 |

| 强度 | 数量 |
|---:|---:|
| 1 | 9,501 |
| 2 | 1,800 |
| 3 | 100 |
| 6 | 2 |
| 7 | 1 |

### 每个档案的本体天体数

| 天体数 | 档案数 |
|---:|---:|
| 1 | 10,900 |
| 2 | 195 |
| 3 | 126 |
| 4 | 95 |
| 5 | 41 |
| 6 | 36 |
| 7 | 11 |

### 天体类型（world_type）

仅统计档案本体天体（恒星档案的星系预览天体不计入）：

| 类型 | 数量 |
|---|---:|
| 无气天体 airless_body | 1,484 |
| 金属世界 metallic_world | 1,281 |
| 冰冻世界 ice_world | 1,196 |
| 气态巨行星 gas_giant | 1,176 |
| 自然宜居世界 natural_habitat | 1,123 |
| 熔岩世界 lava_world | 1,044 |
| 荒漠世界 desert_world | 1,012 |
| 海洋世界 ocean_world | 995 |
| 生态盆地 ecology_basin | 788 |
| 星云平台 nebula_platform | 492 |
| 黑洞 black_hole | 42 |
| 中子星 neutron_star | 39 |

### 星系类型

| 类型 | 数量 |
|---|---:|
| 宜居带 habitable_belt | 4,146 |
| 炽亮恒星 hot_bright | 2,252 |
| 次巨星熔岩带 subgiant_lava | 1,358 |
| 热星气态带 hot_star_gas | 1,346 |
| 红矮星冰带 red_dwarf_ice | 1,335 |
| 星云 nebula | 492 |
| 恒星遗迹 remnant | 218 |
| 卫星群 moon_cluster | 113 |
| 双星潮汐 binary_tidal | 94 |
| 环状文明 ring_civilization | 50 |

### 资源（包含该资源的档案数）

| 资源 | 档案数 | 资源 | 档案数 |
|---|---:|---|---:|
| 碳 carbon | 7,082 | 铜矿 copper_ore | 7,082 |
| 金属 metal | 7,082 | 硅矿 silica_ore | 7,082 |
| 钛矿 titanium_ore | 7,082 | 冰 ice | 6,100 |
| 地热流体 geothermal_fluid | 2,866 | 挥发性风化层 volatile_regolith | 1,284 |
| 大气催化剂 atmospheric_catalyst | 1,822 | 温带生物质 temperate_biomass | 1,822 |
| 磁通矿 magnetic_flux_ore | 1,167 | 远洋矿物浆 pelagic_mineral_slurry | 968 |
| 低温卤水 cryogenic_brine | 1,158 | 氦-3 同位素 helium3_isotope | 1,176 |
| 地幔晶体 mantle_crystal | 1,044 | 太阳盐 solar_salt | 1,012 |
| 电离星云尘埃 ionized_nebula_dust | 492 | 脉冲星同位素 pulsar_isotope | 39 |
| 奇异物质痕迹 exotic_matter_trace | 42 | 居住区再生材料 habitat_reclaimate | 50 |

### 其他

- 槽位 2 个：`incorporated`、`incorporated_planet_2`（均为奇迹行星）
- 抽取回执 11,404 条，放置回执 5 条
- 退役世界 3 个，待收养 0
- 保底记录覆盖强度 1、2、3、6、7

---

## 版本迁移记录

| 项目 | 旧版 | 新版 |
|---|---|---|
| 文件大小 | 158,012,295 字节 | 9,644,131 字节 |
| 外层格式 | v25，明文 | v31，`payload` + `storage` |
| 载荷编码 | 无 | base64 + brotli |
| 内层格式 | v25 | v42 |
| 场景 | — | `civilization-ark-sandbox` |
| 档案数 | 9,902 | 11,404（+15.2%） |
| 档案本体天体数 | 13,788 | 12,546（恒星档案按 1 个本体计） |
| 行星 / 恒星 / 星系 | 7,671 / 1,643 / 588 | 8,860 / 1,874 / 670 |
| 普通 / 罕见 / 稀有 / 奇迹 | 7,523 / 1,718 / 545 / 116 | 8,667 / 1,977 / 628 / 132 |
| revision | 9,906 | 11,409 |
| 强度上限 | 6 | 7 |

迁移时修改的点：

1. `starsea_parser.py` 增加 `expand_payload()` / `load_save()`，兼容压缩与明文两种存档
2. 新增 `world_count`，`list` / `show` / CSV 输出 `template.worlds` 数量（恒星档案中包含星系预览天体，不等于档案本体天体数）
3. `summary` 输出存档格式、场景、规则版本、压缩信息
4. `build_starsea_dashboard.py` 的 `body`：行星/星系档案取 `len(worlds)`，恒星档案取 `body_count`（恒星本体），payload 增加 `worldCount` / `saveFormat` / `scenario` / `rulesVersion`
5. 仪表盘顶栏显示场景，页脚显示存档格式与规则版本
6. 强度筛选改为动态生成（1–7）
7. 网页版载入器对压缩存档给出明确提示

---

## 验证记录

使用无头 Chrome 注入 DOM 测试脚本，等待页面初始化后读取真实 DOM：

```bash
chrome --headless=new --disable-gpu --window-size=1480,1000 \
  --virtual-time-budget=8000 --dump-dom file:///.../_test.html
```

测试项与结果：

| 测试 | 结果 |
|---|---|
| 初始档案数 | 11,404 档案 / 12,546 本体天体 |
| 行星筛选 | 8,860 档案（每行一个行星本体） |
| 恒星筛选 | 1,874 档案（每行一颗恒星本体） |
| 星系筛选 | 670 档案（每行一个星系，内含天体不拆行） |
| 黑洞天体类型筛选 | 42 档案（含黑洞天体的行星/星系档案） |
| 搜索范围 = 创建序列，关键词 11404 | 1 个档案，行为白矮星本体 |
| 资源下拉 | 展开/收起正常，面板显示主采矿产物与合计 |
| 详情抽屉 | 打开正常，资源区块默认折叠 |
| 强度选项 | 1–7 |
| 暗色主题 | 浅/深两套配色均正常渲染 |
| JS 错误 | 0 |

同时对图表与天体表截图检查了标签碰撞、溢出、暗色对比度与表格布局。

---

## 已知限制与后续方向

### 已知限制

- **浏览器解压新版存档占用内存**：内嵌 WASM 解码器可解压，但 227 MB JSON 的解析在低配机器上可能较慢；CLI 数据版更稳
- **内嵌数据版单文件较大**：`starsea_dashboard_data.html` 约 11 MB；解码 227 MB JSON 时 Python 峰值内存较高
- **天体标签重复**：源数据只有 `S000001-P01`…`P07`，档案表身份列使用短档案 id，完整 id 在单元格提示与详情抽屉中
- **只读**：不修改存档，不做回写
- **图表与表格均按档案聚合**：每个档案一行（行星/恒星本体/整个星系），星系内含天体不再拆行；恒星档案的 `template.worlds` 星系预览天体仅在详情抽屉中展示
- **无时间轴**：`created_at_step` 已解析，但尚未用于趋势图

### 可扩展方向

- 用 `created_at_step` 做抽取时间线 / 强度累计曲线
- 资源共现矩阵（哪些材料经常一起出现）
- 槽位对比与“已放置”标记
- 按星系聚合的距离分布图
- ~~内嵌 WebAssembly brotli 解码器，让网页版直接读新版存档~~（已完成，见 `src/vendor/brotli-dec-wasm/`）
- 导出天体级 CSV 之外的 JSON / Excel
- 把重复的枚举字典抽成共享 JSON，供 Python 与 JS 共用

---

## 附：数据来源说明

- `data/m0-slot.json` 为游戏导出的单槽存档，包含 `universe.cosmic_starsea`
- 本工具只读取该文件，不访问游戏进程或网络
- `dist/starsea_dashboard.html` 为空壳，可分发后在网页里载入任意存档
- `dist/starsea_dashboard_data.html` 为自包含离线文件，可直接分发（内含当前存档统计结果）
