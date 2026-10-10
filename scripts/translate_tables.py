"""Translate fixed-stride name tables via veekun reference names.

zh-Hans (lang 12) / zh-Hant (lang 4) name -> English (lang 9). Names longer
than the field are taken from text/en/abbrev.json (hand-made), else reported.
Entries with no reference match are listed in build/tables_unmatched.json for
manual translation in text/en/tables_manual/<name>.json ({index: english}).

Usage: python3 scripts/translate_tables.py
"""
import csv
import json
import os
from collections import defaultdict

REF = {
    "species": ("species", "pokemon_species_id"),
    "moves": ("move", "move_id"),
    "abilities": ("ability", "ability_id"),
    "items": ("item", "item_id"),
    "items2": ("item", "item_id"),
    "types": ("type", "type_id"),
    "types_old": ("type", "type_id"),
}
EN, ZH_HANS, ZH_HANT = "9", "12", "4"


def ref_map(kind, key):
    by_id = defaultdict(dict)
    for r in csv.DictReader(open(f"data/ref/{kind}_names.csv", encoding="utf-8")):
        by_id[r[key]][r["local_language_id"]] = r["name"]
    zh2en = {}
    for names in by_id.values():
        en = names.get(EN)
        if not en:
            continue
        for lang in (ZH_HANT, ZH_HANS):  # Hans wins on conflicts
            if lang in names:
                zh2en[names[lang]] = en
    return zh2en


def genus_map():
    by_id = defaultdict(dict)
    for r in csv.DictReader(open("data/ref/species_names.csv", encoding="utf-8")):
        by_id[r["pokemon_species_id"]][r["local_language_id"]] = r["genus"]
    zh2en = {}
    for g in by_id.values():
        en = g.get(EN, "").removesuffix(" Pokémon")
        for lang in (ZH_HANT, ZH_HANS):
            zh = g.get(lang, "").removesuffix("宝可梦").removesuffix("寶可夢")
            if en and zh:
                zh2en[zh] = en
    return zh2en


def fix_case(name, en):
    # Types are shown in 6-char boxes; keep vanilla FR uppercase style there.
    return en.upper() if name.startswith("types") else en


def main():
    dump = json.load(open("text/zh.json", encoding="utf-8"))["tables"]
    abbrev = json.load(open("text/en/abbrev.json", encoding="utf-8")) \
        if os.path.exists("text/en/abbrev.json") else {}
    os.makedirs("text/en/tables", exist_ok=True)
    unmatched, too_long = {}, {}
    for name, t in dump.items():
        limit = t["size"] - 1
        zh2en = ref_map(*REF[name]) if name in REF else \
            genus_map() if name == "dex_categories" else {}
        manual_path = f"text/en/tables_manual/{name}.json"
        manual = json.load(open(manual_path, encoding="utf-8")) \
            if os.path.exists(manual_path) else {}
        if name == "items2":  # reuse the old table's choices (manual + abbrev)
            old = json.load(open("text/en/tables/items.json", encoding="utf-8"))
            zh2en.update({dump["items"]["entries"][i]: e for i, e in old.items()})
        out, miss = {}, {}
        for idx, zh in t["entries"].items():
            en = manual.get(idx) or (fix_case(name, zh2en[zh]) if zh in zh2en else None)
            if en is None:
                miss[idx] = zh
                continue
            en = abbrev.get(en, en)
            if len(en) > limit:
                too_long.setdefault(name, {})[en] = limit
                continue
            out[idx] = en
        json.dump(out, open(f"text/en/tables/{name}.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        unmatched[name] = miss
        print(f"{name}: {len(out)} ok, {len(miss)} unmatched, "
              f"{len(too_long.get(name, {}))} too long")
    os.makedirs("build", exist_ok=True)
    json.dump({"unmatched": unmatched, "too_long": too_long},
              open("build/tables_unmatched.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
