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
    "BR.pt"
]

shutil.rmtree("output/titleid", ignore_errors=True)
shutil.rmtree("output2/titleid", ignore_errors=True)
os.makedirs("output/titleid")
os.makedirs("output2/titleid")
LIST = {}
LIST2 = {}

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
                added.append(entry_id)
                continue
        else:
            if (entry_id in LIST2.keys()):
                if ((entry["name"] not in LIST2[entry_id]) and (entry_id not in added2)):
                    LIST2[entry_id].append(entry["name"])
                added2.append(entry_id)
                continue            
        if (isOunce == True):
            LIST2[entry_id] = {}
            LIST2[entry_id] = [entry["name"]]
            added2.append(entry_id)
        else: 
            LIST[entry_id] = {}
            if (entry["name"] == "Borderlands: The Handsome Collection"): entry["name"] = "Borderlands 2: Game of the Year Edition"
            LIST[entry_id] = [entry["name"]]
            added.append(entry_id)
        entry = {}
        entry["bannerUrl"] = DUMP[keys[i]]["bannerUrl"]
        entry["iconUrl"] = DUMP[keys[i]]["iconUrl"]
        entry["publisher"] = DUMP[keys[i]]["publisher"]
        entry["screenshots"] = DUMP[keys[i]]["screenshots"]
        entry["releaseDate"] = DUMP[keys[i]]["releaseDate"]
        if (DUMP[keys[i]]["size"] == 0):
            entry["size"] = "Unknown"
        elif (DUMP[keys[i]]["size"] < 1024*1024*1024):
            entry["size"] = "%.0f MiB" % (DUMP[keys[i]]["size"] / (1024*1024))
        else:
            entry["size"] = "%.2f GiB" % (DUMP[keys[i]]["size"] / (1024*1024*1024))
        if (isOunce == False):
            new_file = open("output/titleid/%s.json" % entry_id, "w", encoding="UTF-8")
        else: new_file = open("output2/titleid/%s.json" % entry_id, "w", encoding="UTF-8")
        json.dump(entry, new_file, indent="\t", ensure_ascii=True)
        new_file.close()


missing_games = glob.glob("missing/*.json")
for i in range(len(missing_games)):
    titleid = Path(missing_games[i]).stem
    if (titleid in LIST):
        continue
    file = open(missing_games[i], "r", encoding="UTF-8")
    DUMP = json.load(file)
    file.close()
    LIST[titleid] = [DUMP["name"]]
    entry = {}
    entry["bannerUrl"] = DUMP["bannerUrl"]
    entry["iconUrl"] = DUMP["iconUrl"]
    entry["publisher"] = DUMP["publisher"]
    entry["screenshots"] = DUMP["screenshots"]
    entry["releaseDate"] = DUMP["releaseDate"]
    if (("size" not in DUMP.keys()) or (DUMP["size"] == 0) or (DUMP["size"] == None)):
        entry["size"] = "Unknown"
    else: entry["size"] = DUMP["size"]
    new_file = open("output/titleid/%s.json" % titleid, "w", encoding="UTF-8")
    json.dump(entry, new_file, indent="\t", ensure_ascii=True)
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
print("Done.")
















