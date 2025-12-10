import json
import os
import shutil
import lzma
import glob
from pathlib import Path

files = [
    "US.en",
    "GB.en",
    "JP.ja",
    "FR.fr",
    "DE.de",
    "ES.es",
    "IT.it",
    "NL.nl",
    "CA.fr",
    "PT.pt",
    "RU.ru",
    "KR.ko",
    "HK.zh",
    "BR.pt",
    
    "PL.en",
    "AR.en",
    "AR.es",
    "AT.de",
    "AU.en",
    "BE.fr",
    "BE.nl",
    "BG.en",
    "BR.en",
    "CA.en",
    "CH.de",
    "CH.fr",
    "CH.it",
    "CL.en",
    "CL.es",
    "CN.en",
    "CN.zh",
    "CO.en",
    "CO.es",
    "CY.en",
    "CZ.en",
    "DK.en",
    "EE.en",
    "FI.en",
    "GR.en",
    "HR.en",
    "HU.en",
    "IE.en",
    "IL.en",
    "JP.en",
    "LT.en",
    "LU.de",
    "LU.fr",
    "LV.en",
    "MT.en",
    "MX.en",
    "NO.en",
    "NZ.en",
    "PE.en",
    "PE.es",
    "RO.en",
    "SE.en",
    "SI.en",
    "SK.en",
    "US.es",
    "ZA.en"
]

shutil.rmtree("output/titleid", ignore_errors=True)
shutil.rmtree("output2/titleid", ignore_errors=True)
os.makedirs("output/titleid")
os.makedirs("output2/titleid")
LIST = {}
LIST_REGIONS = {}
LIST2 = {}
LIST2_REGIONS = {}

for x in range(len(files)):

    file = open("titledb/%s.json" % files[x], "r", encoding="UTF-8")
    DUMP = json.load(file)
    file.close()

    keys = list(DUMP.keys())

    num = len(keys)
    print("Processing", files[x])
    added = []
    added2 = []
    for i in range(num):
        entry = DUMP[keys[i]]
        entry_id = DUMP[keys[i]]["id"]
        if (entry_id == None):
            continue
        ending = int("0x" + entry_id[12:16], base=16)
        if (ending % 0x2000 != 0):
            continue
        if (entry["publisher"] == None):
            continue
        isOunce = False
        if (entry_id[0:2] == "04"):
            isOunce = True
        if (isOunce == False):
            if (entry_id in LIST.keys()):
                if ((entry["name"] not in LIST[entry_id]) and (entry_id not in added)):
                    LIST[entry_id].append(entry["name"])
                if ((files[x][0:2] not in LIST_REGIONS[entry_id]) and (entry_id not in added)):
                    LIST_REGIONS[entry_id].append(files[x][0:2])
                added.append(entry_id)
                continue
        else:
            if (entry_id in LIST2.keys()):
                if ((entry["name"] not in LIST2[entry_id]) and (entry_id not in added2)):
                    LIST2[entry_id].append(entry["name"])
                if ((files[x][0:2] not in LIST2_REGIONS[entry_id]) and (entry_id not in added2)):
                    LIST2_REGIONS[entry_id].append(files[x][0:2])
                added2.append(entry_id)
                continue            
        if (isOunce == True):
            LIST2[entry_id] = [entry["name"]]
            LIST2_REGIONS[entry_id] = [files[x][0:2]]
            added2.append(entry_id)
        else: 
            if (entry["name"] == "Borderlands: The Handsome Collection"): entry["name"] = "Borderlands 2: Game of the Year Edition"
            LIST[entry_id] = [entry["name"]]
            LIST_REGIONS[entry_id] = [files[x][0:2]]
            added.append(entry_id)
        
        # 提取新增的字段
        entry_output = {}
        entry_output["bannerUrl"] = DUMP[keys[i]]["bannerUrl"]
        entry_output["iconUrl"] = DUMP[keys[i]]["iconUrl"]
        entry_output["publisher"] = DUMP[keys[i]]["publisher"]
        entry_output["screenshots"] = DUMP[keys[i]]["screenshots"]
        entry_output["releaseDate"] = DUMP[keys[i]]["releaseDate"]
        
        # 提取游戏类型(category)
        entry_output["category"] = DUMP[keys[i]].get("category", [])
        
        # 提取游戏介绍(intro)
        entry_output["intro"] = DUMP[keys[i]].get("intro", "")
        
        # 提取游戏详细描述(description) - 新增
        entry_output["description"] = DUMP[keys[i]].get("description", "")
        
        # 提取游戏语言(languages)
        entry_output["languages"] = DUMP[keys[i]].get("languages", [])
        
        # 提取最大游玩人数(numberOfPlayers)
        entry_output["numberOfPlayers"] = DUMP[keys[i]].get("numberOfPlayers", 1)
        
        # 保持原有的size处理逻辑
        if (DUMP[keys[i]]["size"] == 0):
            entry_output["size"] = "Unknown"
        elif (DUMP[keys[i]]["size"] < 1024*1024*1024):
            entry_output["size"] = "%.0f MiB" % (DUMP[keys[i]]["size"] / (1024*1024))
        else:
            entry_output["size"] = "%.2f GiB" % (DUMP[keys[i]]["size"] / (1024*1024*1024))
        
        if (isOunce == False):
            new_file = open("output/titleid/%s.json" % entry_id, "w", encoding="UTF-8")
        else: 
            new_file = open("output2/titleid/%s.json" % entry_id, "w", encoding="UTF-8")
        json.dump(entry_output, new_file, indent="\t", ensure_ascii=True)
        new_file.close()


missing_games = glob.glob("missing/*.json")
for i in range(len(missing_games)):
    titleid = Path(missing_games[i]).stem
    if (titleid in LIST):
        continue
    file = open(missing_games[i], "r", encoding="UTF-8")
    DUMP = json.load(file)
    file.close()
    if isinstance(DUMP["name"], list):
        LIST[titleid] = DUMP["name"]
    else:
        LIST[titleid] = [DUMP["name"]]
    
    # 处理缺失游戏的数据提取
    entry_output = {}
    entry_output["bannerUrl"] = DUMP.get("bannerUrl", "")
    entry_output["iconUrl"] = DUMP.get("iconUrl", "")
    entry_output["publisher"] = DUMP.get("publisher", "")
    entry_output["screenshots"] = DUMP.get("screenshots", [])
    entry_output["releaseDate"] = DUMP.get("releaseDate", "")
    
    # 提取新增的字段
    entry_output["category"] = DUMP.get("category", [])
    entry_output["intro"] = DUMP.get("intro", "")
    entry_output["description"] = DUMP.get("description", "")
    entry_output["languages"] = DUMP.get("languages", [])
    entry_output["numberOfPlayers"] = DUMP.get("numberOfPlayers", 1)
    
    if (("size" not in DUMP.keys()) or (DUMP["size"] == 0) or (DUMP["size"] == None)):
        entry_output["size"] = "Unknown"
    else: 
        # 如果size是数字，转换为合适的格式
        if isinstance(DUMP["size"], (int, float)):
            if DUMP["size"] < 1024*1024*1024:
                entry_output["size"] = "%.0f MiB" % (DUMP["size"] / (1024*1024))
            else:
                entry_output["size"] = "%.2f GiB" % (DUMP["size"] / (1024*1024*1024))
        else:
            entry_output["size"] = DUMP["size"]
    
    new_file = open("output/titleid/%s.json" % titleid, "w", encoding="UTF-8")
    json.dump(entry_output, new_file, indent="\t", ensure_ascii=True)
    new_file.close()

print("                        ")
print("Dumping...")
new_file = open("output/main.json", "w", encoding="UTF-8")
json.dump(LIST, new_file, ensure_ascii=False)
new_file.close()
with lzma.open("output/main.json.xz", "w", format=lzma.FORMAT_XZ) as f:
    f.write(json.dumps(LIST, ensure_ascii=False).encode("UTF-8"))
new_file = open("output2/main.json", "w", encoding="UTF-8")
json.dump(LIST2, new_file, ensure_ascii=False)
new_file.close()
with lzma.open("output2/main.json.xz", "w", format=lzma.FORMAT_XZ) as f:
    f.write(json.dumps(LIST2, ensure_ascii=False).encode("UTF-8"))
new_file = open("output/main_regions.json", "w", encoding="UTF-8")
json.dump(LIST_REGIONS, new_file, ensure_ascii=False)
new_file.close()
with lzma.open("output/main_regions.json.xz", "w", format=lzma.FORMAT_XZ) as f:
    f.write(json.dumps(LIST_REGIONS, ensure_ascii=False).encode("UTF-8"))
new_file = open("output2/main_regions.json", "w", encoding="UTF-8")
json.dump(LIST2_REGIONS, new_file, ensure_ascii=False)
new_file.close()
with lzma.open("output2/main_regions.json.xz", "w", format=lzma.FORMAT_XZ) as f:
    f.write(json.dumps(LIST2_REGIONS, ensure_ascii=False).encode("UTF-8"))
print("Done.")
