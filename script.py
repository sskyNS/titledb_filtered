import json
import os
import shutil
import lzma

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
os.makedirs("output/titleid")
LIST = {}

for x in range(len(files)):

    file = open("titledb/%s.json" % files[x], "r", encoding="UTF-8")
    DUMP = json.load(file)
    file.close()

    keys = list(DUMP.keys())

    num = len(keys)
    print("Processing", files[x])
    added = []
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
        if (entry_id in LIST.keys()):
            if ((entry["name"] not in LIST[entry_id]) and (entry_id not in added)):
                LIST[entry_id].append(entry["name"])
            added.append(entry_id)
            continue
        LIST[entry_id] = {}
        LIST[entry_id] = [entry["name"]]
        added.append(entry_id)
        entry = {}
        entry["bannerUrl"] = DUMP[keys[i]]["bannerUrl"]
        entry["iconUrl"] = DUMP[keys[i]]["iconUrl"]
        entry["publisher"] = DUMP[keys[i]]["publisher"]
        entry["screenshots"] = DUMP[keys[i]]["screenshots"]
        entry["releaseDate"] = DUMP[keys[i]]["releaseDate"]
        if (DUMP[keys[i]]["size"] < 1024*1024*1024):
            entry["size"] = "%.0f MiB" % (DUMP[keys[i]]["size"] / (1024*1024))
        else:
            entry["size"] = "%.2f GiB" % (DUMP[keys[i]]["size"] / (1024*1024*1024))
        new_file = open("output/titleid/%s.json" % DUMP[keys[i]]["id"], "w", encoding="UTF-8")
        json.dump(entry, new_file, indent="\t", ensure_ascii=True)
        new_file.close()

print("                        ")
print("Dumping...")
new_file = open("output/main.json", "w", encoding="UTF-8")
json.dump(LIST, new_file, ensure_ascii=False)
new_file.close()
with lzma.open("output/main.json.xz", "w", format=lzma.FORMAT_XZ) as f:
    f.write(json.dumps(LIST, ensure_ascii=False).encode("UTF-8"))
print("Done.")
