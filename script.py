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
for x in range(len(files)):
    with open("titledb/%s.json" % files[x], "r", encoding="UTF-8") as f:
        DUMP = json.load(f)

    keys = list(DUMP.keys())
    num = len(keys)
    print("Processing", files[x])
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
                if files[x][0:2] not in LIST_REGIONS[entry_id] and entry_id not in added:
                    LIST_REGIONS[entry_id].append(files[x][0:2])
                added.append(entry_id)
                continue
        else:
            if entry_id in LIST2:
                if entry["name"] not in LIST2[entry_id] and entry_id not in added2:
                    LIST2[entry_id].append(entry["name"])
                if files[x][0:2] not in LIST2_REGIONS[entry_id] and entry_id not in added2:
                    LIST2_REGIONS[entry_id].append(files[x][0:2])
                added2.append(entry_id)
                continue

        if isOunce:
            LIST2[entry_id] = [entry["name"]]
            LIST2_REGIONS[entry_id] = [files[x][0:2]]
            NS2UIDs.append(entry.get("nsuId"))
            added2.append(entry_id)
        else:
            if entry["name"] == "Borderlands: The Handsome Collection":
                entry["name"] = "Borderlands 2: Game of the Year Edition"
            LIST[entry_id] = [entry["name"]]
            LIST_REGIONS[entry_id] = [files[x][0:2]]
            NSUIDs.append(entry.get("nsuId"))
            added.append(entry_id)

        entry_output = {}
        entry_output["bannerUrl"] = entry.get("bannerUrl", "")
        entry_output["iconUrl"] = entry.get("iconUrl", "")
        entry_output["publisher"] = entry.get("publisher", "")
        entry_output["screenshots"] = entry.get("screenshots", [])
        entry_output["releaseDate"] = entry.get("releaseDate", "")
        entry_output["category"] = entry.get("category", [])
        entry_output["intro"] = entry.get("intro", "")
        entry_output["description"] = entry.get("description", "")
        entry_output["languages"] = entry.get("languages", [])
        entry_output["numberOfPlayers"] = entry.get("numberOfPlayers", 1)
        entry_output["rating"] = entry.get("rating", "Unknown")
        entry_output["ratingContent"] = entry.get("ratingContent", [])
        entry_output["dlcs"] = entry.get("dlcs", entry.get("dlc", []))

        size = entry.get("size", 0)
        if size == 0:
            entry_output["size"] = "Unknown"
        elif size < 1024 * 1024 * 1024:
            entry_output["size"] = "%.0f MiB" % (size / (1024 * 1024))
        else:
            entry_output["size"] = "%.2f GiB" % (size / (1024 * 1024 * 1024))

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

# ========== 合并 missing 手动补充数据 ==========
missing_games = glob.glob("missing/*.json")
for path in missing_games:
    titleid = Path(path).stem
    if titleid in LIST:
        continue
    with open(path, "r", encoding="UTF-8") as f:
        DUMP = json.load(f)

    if isinstance(DUMP["name"], list):
        LIST[titleid] = DUMP["name"]
    else:
        LIST[titleid] = [DUMP["name"]]

    entry_output = {}
    entry_output["bannerUrl"] = DUMP.get("bannerUrl", "")
    entry_output["iconUrl"] = DUMP.get("iconUrl", "")
    entry_output["publisher"] = DUMP.get("publisher", "")
    entry_output["screenshots"] = DUMP.get("screenshots", [])
    entry_output["releaseDate"] = DUMP.get("releaseDate", "")
    entry_output["category"] = DUMP.get("category", [])
    entry_output["intro"] = DUMP.get("intro", "")
    entry_output["description"] = DUMP.get("description", "")
    entry_output["languages"] = DUMP.get("languages", [])
    entry_output["numberOfPlayers"] = DUMP.get("numberOfPlayers", 1)
    entry_output["rating"] = DUMP.get("rating", "Unknown")
    entry_output["ratingContent"] = DUMP.get("ratingContent", [])
    entry_output["dlcs"] = DUMP.get("dlcs", DUMP.get("dlc", []))

    size = DUMP.get("size", 0)
    if size is None or size == 0:
        entry_output["size"] = "Unknown"
    elif isinstance(size, (int, float)):
        if size < 1024 * 1024 * 1024:
            entry_output["size"] = "%.0f MiB" % (size / (1024 * 1024))
        else:
            entry_output["size"] = "%.2f GiB" % (size / (1024 * 1024 * 1024))
    else:
        entry_output["size"] = str(size)

    if titleid.startswith("0400"):
        output_path = "output2/titleid/%s.json" % titleid
    else:
        output_path = "output/titleid/%s.json" % titleid
    with open(output_path, "w", encoding="UTF-8") as f:
        json.dump(entry_output, f, indent="\t", ensure_ascii=True)

# ========== 合并 eshopScrapper 数据 ==========
eshop_games = glob.glob("eshopScrapper/output/titleid/*.json")
for path in eshop_games:
    titleid = Path(path).stem
    isOunce = titleid.startswith("0400")

    if isOunce and titleid in LIST2:
        continue
    if not isOunce and titleid in LIST:
        continue

    with open(path, "r", encoding="UTF-8") as f:
        DUMP = json.load(f)

    name = DUMP.get("name", "")
    if isinstance(name, list):
        if isOunce:
            LIST2[titleid] = name
        else:
            LIST[titleid] = name
    else:
        if isOunce:
            LIST2[titleid] = [name]
        else:
            LIST[titleid] = [name]

    entry_output = {}
    entry_output["bannerUrl"] = DUMP.get("bannerUrl", "")
    entry_output["iconUrl"] = DUMP.get("iconUrl", "")
    entry_output["publisher"] = DUMP.get("publisher", "")
    entry_output["screenshots"] = DUMP.get("screenshots", [])
    entry_output["releaseDate"] = DUMP.get("releaseDate", "")
    entry_output["category"] = DUMP.get("category", [])
    entry_output["intro"] = DUMP.get("intro", "")
    entry_output["description"] = DUMP.get("description", "")
    entry_output["languages"] = DUMP.get("languages", [])
    entry_output["numberOfPlayers"] = DUMP.get("numberOfPlayers", 1)
    entry_output["rating"] = DUMP.get("rating", "Unknown")
    entry_output["ratingContent"] = DUMP.get("ratingContent", [])
    entry_output["dlcs"] = DUMP.get("dlcs", DUMP.get("dlc", []))

    size = DUMP.get("size", 0)
    if size is None or size == 0:
        entry_output["size"] = "Unknown"
    elif isinstance(size, (int, float)):
        if size < 1024 * 1024 * 1024:
            entry_output["size"] = "%.0f MiB" % (size / (1024 * 1024))
        else:
            entry_output["size"] = "%.2f GiB" % (size / (1024 * 1024 * 1024))
    else:
        entry_output["size"] = str(size)

    if isOunce:
        output_path = "output2/titleid/%s.json" % titleid
    else:
        output_path = "output/titleid/%s.json" % titleid
    with open(output_path, "w", encoding="UTF-8") as f:
        json.dump(entry_output, f, indent="\t", ensure_ascii=True)

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
