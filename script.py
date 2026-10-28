import json
import os
import shutil
import lzma
import glob
import sys
from pathlib import Path
import requests
class RateLimitError(Exception):
    """Nintendo API 限流，跳过剩余检查"""
    pass
files = [
    "US.en", "GB.en", "JP.ja", "FR.fr", "DE.de", "ES.es", "IT.it",
    "NL.nl", "CA.fr", "PT.pt", "RU.ru", "KR.ko", "HK.zh", "BR.pt",
    "PL.en", "AR.en", "AR.es", "AT.de", "AU.en", "BE.fr", "BE.nl",
    "BG.en", "BR.en", "CA.en", "CH.de", "CH.fr", "CH.it", "CL.en",
    "CL.es", "CN.en", "CN.zh", "CO.en", "CO.es", "CY.en", "CZ.en",
    "DK.en", "EE.en", "FI.en", "GR.en", "HR.en", "HU.en", "IE.en",
    "IL.en", "JP.en", "LT.en", "LU.de", "LU.fr", "LV.en", "MT.en",
    "MX.en", "NO.en", "NZ.en", "PE.en", "PE.es", "RO.en", "SE.en",
    "SI.en", "SK.en", "US.es", "ZA.en"
]
REGIONS = ["MY", "SG", "TH", "TW"]


def checkTitleid(titleid: str, region: str) -> bool:
    """通过 Nintendo eShop API 验证某个区域是否有该游戏"""
    url = f"https://ec.nintendo.com/apps/{titleid}/{region}"
    try:
        with requests.head(url, stream=True, allow_redirects=False, timeout=10) as response:
            status_code = response.status_code
            if status_code == 303:
                print(f"  OK {region} {titleid}")
                return True
            elif status_code == 403:
                print("  Rate limited by Nintendo API, skipping further checks.")
                raise RateLimitError()
            else:
                print(f"  -- {region} {titleid}: {status_code}")
                return False
    except requests.RequestException as e:
        print(f"  !! {region} {titleid}: network error ({e}), assuming unavailable")
        return False


def is_empty(value) -> bool:
    """判断字段是否为「无有效值」，用于判断能否被其它数据源补齐"""
    return value is None or value == "" or value == [] or value == {} or value == 0 or value == "Unknown"


def build_entry(dump: dict) -> dict:
    """把任意上游数据源的一条记录统一转换成输出格式"""
    entry_output = {}
    entry_output["bannerUrl"] = dump.get("bannerUrl", "")
    entry_output["iconUrl"] = dump.get("iconUrl", "")
    entry_output["publisher"] = dump.get("publisher", "")
    entry_output["screenshots"] = dump.get("screenshots", [])
    entry_output["releaseDate"] = dump.get("releaseDate", "")
    entry_output["category"] = dump.get("category", [])
    entry_output["intro"] = dump.get("intro", "")
    entry_output["description"] = dump.get("description", "")
    entry_output["languages"] = dump.get("languages", [])
    entry_output["numberOfPlayers"] = dump.get("numberOfPlayers", 1)
    entry_output["rating"] = dump.get("rating", "Unknown")
    entry_output["ratingContent"] = dump.get("ratingContent", [])
    entry_output["dlcs"] = dump.get("dlcs", dump.get("dlc", []))
    size = dump.get("size", 0)
    if size is None or size == 0:
        entry_output["size"] = "Unknown"
    elif isinstance(size, (int, float)):
        if size < 1024 * 1024 * 1024:
            entry_output["size"] = "%.0f MiB" % (size / (1024 * 1024))
        else:
            entry_output["size"] = "%.2f GiB" % (size / (1024 * 1024 * 1024))
    else:
        entry_output["size"] = str(size)
    return entry_output


ENTRY_TEMPLATE = {
    "bannerUrl": "",
    "iconUrl": "",
    "publisher": "",
    "screenshots": [],
    "releaseDate": "",
    "category": [],
    "intro": "",
    "description": "",
    "languages": [],
    "numberOfPlayers": 1,
    "rating": "Unknown",
    "ratingContent": [],
    "dlcs": [],
    "size": "Unknown",
}


def merge_into_output(out_path: str, new_entry: dict) -> bool:
    """把新数据合并进已存在的 output 文件：
    - 已有字段为空时才用新值补齐（不覆盖有效数据）
    - 列表字段做并集去重
    - 始终保证输出文件包含全部标准字段，避免下游读取缺键
    返回是否产生了实际变化
    """
    cur = {}
    existed = os.path.isfile(out_path)
    if existed:
        try:
            with open(out_path, "r", encoding="UTF-8") as f:
                cur = json.load(f)
        except (ValueError, OSError):
            cur = {}
    for key, default in ENTRY_TEMPLATE.items():
        if key not in cur:
            cur[key] = default.copy() if isinstance(default, list) else default
    changed = False
    for key, value in new_entry.items():
        if is_empty(value):
            continue
        old = cur.get(key)
        if is_empty(old):
            cur[key] = value
            changed = True
        elif isinstance(value, list) and isinstance(old, list):
            added = [x for x in value if x not in old]
            if added:
                old.extend(added)
                changed = True
    if changed or not existed:
        with open(out_path, "w", encoding="UTF-8") as f:
            json.dump(cur, f, indent="\t", ensure_ascii=True)
    return changed


# ========== 上游数据存在性检查（上游挂了也不清空已有数据）==========
existing_files = [f for f in files if os.path.isfile("titledb/%s.json" % f)]
if len(existing_files) < 10:
    print("!! titledb 上游数据缺失或不完整（仅 %d 个区域文件），本次跳过数据重建，保留仓库中已有的 output/ 数据" % len(existing_files))
    print("!! 工作流仍会继续打包并发布现有数据，保证下载链接可用")
    sys.exit(0)

shutil.rmtree("output/titleid", ignore_errors=True)
shutil.rmtree("output2/titleid", ignore_errors=True)
os.makedirs("output/titleid", exist_ok=True)
os.makedirs("output2/titleid", exist_ok=True)
LIST = {}
LIST_REGIONS = {}
NSUIDs = []
LIST2 = {}
LIST2_REGIONS = {}
NS2UIDs = []
# ========== 处理 titledb 上游数据 ==========
for region_file in existing_files:
    with open("titledb/%s.json" % region_file, "r", encoding="UTF-8") as f:
        DUMP = json.load(f)
    keys = list(DUMP.keys())
    num = len(keys)
    print("Processing", region_file)
    region_code = region_file[0:2]
    added = []
    added2 = []
    for i in range(num):
        entry = DUMP[keys[i]]
        entry_id = entry.get("id")
        if entry_id is None:
            continue
        ending = int("0x" + entry_id[12:16], base=16)
        if ending % 0x2000 != 0:
            continue
        if entry.get("publisher") is None:
            continue
        isOunce = entry_id[0:2] == "04"
        if not isOunce:
            if entry_id in LIST:
                if entry["name"] not in LIST[entry_id] and entry_id not in added:
                    LIST[entry_id].append(entry["name"])
                if region_code not in LIST_REGIONS[entry_id] and entry_id not in added:
                    LIST_REGIONS[entry_id].append(region_code)
                added.append(entry_id)
                continue
        else:
            if entry_id in LIST2:
                if entry["name"] not in LIST2[entry_id] and entry_id not in added2:
                    LIST2[entry_id].append(entry["name"])
                if region_code not in LIST2_REGIONS[entry_id] and entry_id not in added2:
                    LIST2_REGIONS[entry_id].append(region_code)
                added2.append(entry_id)
                continue
        if isOunce:
            LIST2[entry_id] = [entry["name"]]
            LIST2_REGIONS[entry_id] = [region_code]
            NS2UIDs.append(entry.get("nsuId"))
            added2.append(entry_id)
        else:
            if entry["name"] == "Borderlands: The Handsome Collection":
                entry["name"] = "Borderlands 2: Game of the Year Edition"
            LIST[entry_id] = [entry["name"]]
            LIST_REGIONS[entry_id] = [region_code]
            NSUIDs.append(entry.get("nsuId"))
            added.append(entry_id)
        entry_output = build_entry(entry)
        if isOunce:
            output_path = "output2/titleid/%s.json" % entry_id
        else:
            output_path = "output/titleid/%s.json" % entry_id
        with open(output_path, "w", encoding="UTF-8") as f:
            json.dump(entry_output, f, indent="\t", ensure_ascii=True)
# 保存 NSUIDs
with open("output/nsuIDs.json", "w", encoding="UTF-8") as f:
    json.dump(NSUIDs, f, ensure_ascii=False)
with open("output2/nsuIDs.json", "w", encoding="UTF-8") as f:
    json.dump(NS2UIDs, f, ensure_ascii=False)
# ========== Nintendo API 区域验证（带缓存）==========
LIST_REGIONS_ALT = {}
LIST2_REGIONS_ALT = {}
if os.path.isfile("output/main_regions_alt.json"):
    with open("output/main_regions_alt.json", "r", encoding="UTF-8") as f:
        LIST_REGIONS_ALT = json.load(f)
if os.path.isfile("output2/main_regions_alt.json"):
    with open("output2/main_regions_alt.json", "r", encoding="UTF-8") as f:
        LIST2_REGIONS_ALT = json.load(f)
print("\nVerifying regions via Nintendo API (output/)...")
try:
    titleids = list(LIST_REGIONS.keys())
    for titleid in titleids:
        if titleid in LIST_REGIONS_ALT:
            cache = LIST_REGIONS_ALT[titleid]
            for region in REGIONS:
                if region in cache.get("True", []):
                    if region not in LIST_REGIONS[titleid]:
                        LIST_REGIONS[titleid].append(region)
                elif region in cache.get("False", []):
                    continue
                else:
                    if checkTitleid(titleid, region):
                        LIST_REGIONS[titleid].append(region)
                        cache.setdefault("True", []).append(region)
                    else:
                        cache.setdefault("False", []).append(region)
        else:
            LIST_REGIONS_ALT[titleid] = {"True": [], "False": []}
            for region in REGIONS:
                if checkTitleid(titleid, region):
                    LIST_REGIONS[titleid].append(region)
                    LIST_REGIONS_ALT[titleid]["True"].append(region)
                else:
                    LIST_REGIONS_ALT[titleid]["False"].append(region)
except RateLimitError:
    print("Nintendo API rate limited. Skipping remaining region checks (cached results preserved).")
print("\nVerifying regions via Nintendo API (output2/)...")
try:
    titleids = list(LIST2_REGIONS.keys())
    for titleid in titleids:
        if titleid in LIST2_REGIONS_ALT:
            cache = LIST2_REGIONS_ALT[titleid]
            for region in REGIONS:
                if region in cache.get("True", []):
                    if region not in LIST2_REGIONS[titleid]:
                        LIST2_REGIONS[titleid].append(region)
                elif region in cache.get("False", []):
                    continue
                else:
                    if checkTitleid(titleid, region):
                        LIST2_REGIONS[titleid].append(region)
                        cache.setdefault("True", []).append(region)
                    else:
                        cache.setdefault("False", []).append(region)
        else:
            LIST2_REGIONS_ALT[titleid] = {"True": [], "False": []}
            for region in REGIONS:
                if checkTitleid(titleid, region):
                    LIST2_REGIONS[titleid].append(region)
                    LIST2_REGIONS_ALT[titleid]["True"].append(region)
                else:
                    LIST2_REGIONS_ALT[titleid]["False"].append(region)
except RateLimitError:
    print("Nintendo API rate limited. Skipping remaining region checks (cached results preserved).")
# 保存区域验证缓存
with open("output/main_regions_alt.json", "w", encoding="UTF-8") as f:
    json.dump(LIST_REGIONS_ALT, f, indent="\t")
with open("output2/main_regions_alt.json", "w", encoding="UTF-8") as f:
    json.dump(LIST2_REGIONS_ALT, f, indent="\t")
# ========== 合并 missing 手动补充数据（字段级覆盖/补齐）==========
missing_games = glob.glob("missing/*.json")
missing_added = 0
missing_filled = 0
for path in missing_games:
    titleid = Path(path).stem
    with open(path, "r", encoding="UTF-8") as f:
        DUMP = json.load(f)
    name = DUMP.get("name", "")
    names = name if isinstance(name, list) else [name]
    names = [n for n in names if n]
    if not names:
        continue
    isOunce = titleid.startswith("0400")
    target = LIST2 if isOunce else LIST
    out_path = ("output2" if isOunce else "output") + "/titleid/%s.json" % titleid
    entry_output = build_entry(DUMP)
    if titleid in target:
        for n in names:
            if n not in target[titleid]:
                target[titleid].append(n)
        if merge_into_output(out_path, entry_output):
            missing_filled += 1
    else:
        target[titleid] = list(names)
        with open(out_path, "w", encoding="UTF-8") as f:
            json.dump(entry_output, f, indent="\t", ensure_ascii=True)
        missing_added += 1
print("missing/: 新增 %d 条，补齐 %d 条" % (missing_added, missing_filled))
# ========== 合并 eshopScrapper 数据（字段级覆盖/补齐）==========
eshop_games = glob.glob("eshopScrapper/output/titleid/*.json")
eshop_added = 0
eshop_filled = 0
for path in eshop_games:
    titleid = Path(path).stem
    isOunce = titleid.startswith("0400")
    with open(path, "r", encoding="UTF-8") as f:
        DUMP = json.load(f)
    name = DUMP.get("name", "")
    names = name if isinstance(name, list) else [name]
    names = [n for n in names if n]
    if not names:
        continue
    target = LIST2 if isOunce else LIST
    out_path = ("output2" if isOunce else "output") + "/titleid/%s.json" % titleid
    entry_output = build_entry(DUMP)
    if titleid in target:
        # 已收录的游戏：合并多语言名称，并用 eShop 数据补齐缺失字段
        for n in names:
            if n not in target[titleid]:
                target[titleid].append(n)
        if merge_into_output(out_path, entry_output):
            eshop_filled += 1
    else:
        target[titleid] = list(names)
        with open(out_path, "w", encoding="UTF-8") as f:
            json.dump(entry_output, f, indent="\t", ensure_ascii=True)
        eshop_added += 1
print("eshopScrapper: 新增 %d 条，补齐 %d 条" % (eshop_added, eshop_filled))
# ========== 合并 eshopScrapper 的区域数据 ==========
if os.path.isfile("eshopScrapper/output/main_regions_alt.json"):
    with open("eshopScrapper/output/main_regions_alt.json", "r", encoding="UTF-8") as f:
        DUMP = json.load(f)
    for key in DUMP:
        if key.startswith("0100"):
            if key not in LIST_REGIONS:
                LIST_REGIONS[key] = DUMP[key]
            else:
                for r in DUMP[key]:
                    if r not in LIST_REGIONS[key]:
                        LIST_REGIONS[key].append(r)
        elif key.startswith("0400"):
            if key not in LIST2_REGIONS:
                LIST2_REGIONS[key] = DUMP[key]
            else:
                for r in DUMP[key]:
                    if r not in LIST2_REGIONS[key]:
                        LIST2_REGIONS[key].append(r)
if os.path.isfile("eshopScrapper/output/main_regions_alt2.json"):
    with open("eshopScrapper/output/main_regions_alt2.json", "r", encoding="UTF-8") as f:
        DUMP = json.load(f)
    for key in DUMP:
        if key.startswith("0100"):
            for r in DUMP[key].get("True", []):
                if key not in LIST_REGIONS:
                    LIST_REGIONS[key] = [r]
                elif r not in LIST_REGIONS[key]:
                    LIST_REGIONS[key].append(r)
        elif key.startswith("0400"):
            for r in DUMP[key].get("True", []):
                if key not in LIST2_REGIONS:
                    LIST2_REGIONS[key] = [r]
                elif r not in LIST2_REGIONS[key]:
                    LIST2_REGIONS[key].append(r)
# ========== 输出聚合文件 ==========
print("\nDumping...")
with open("output/main.json", "w", encoding="UTF-8") as f:
    json.dump(LIST, f, ensure_ascii=False)
with lzma.open("output/main.json.xz", "w", format=lzma.FORMAT_XZ) as f:
    f.write(json.dumps(LIST, ensure_ascii=False).encode("UTF-8"))
with open("output2/main.json", "w", encoding="UTF-8") as f:
    json.dump(LIST2, f, ensure_ascii=False)
with lzma.open("output2/main.json.xz", "w", format=lzma.FORMAT_XZ) as f:
    f.write(json.dumps(LIST2, ensure_ascii=False).encode("UTF-8"))
with open("output/main_regions.json", "w", encoding="UTF-8") as f:
    json.dump(LIST_REGIONS, f, ensure_ascii=False)
with lzma.open("output/main_regions.json.xz", "w", format=lzma.FORMAT_XZ) as f:
    f.write(json.dumps(LIST_REGIONS, ensure_ascii=False).encode("UTF-8"))
with open("output2/main_regions.json", "w", encoding="UTF-8") as f:
    json.dump(LIST2_REGIONS, f, ensure_ascii=False)
with lzma.open("output2/main_regions.json.xz", "w", format=lzma.FORMAT_XZ) as f:
    f.write(json.dumps(LIST2_REGIONS, ensure_ascii=False).encode("UTF-8"))
print("Done.")
