"""Package the earlier workbook's frozen inputs and production audit.

This one-time archival step reads the existing project workspace. The new study
itself reproduces from the public files committed under data/raw and data/processed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=ROOT.parent)
    args = parser.parse_args()
    previous = args.workspace / "outputs"
    comp = previous / "mid2023_comprehensive_20261118"
    english = previous / "mid2023_english_20261118"
    first = previous / "mid2023_aircraft_20261118"
    target = ROOT / "data/workbooks"
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    for source in [comp/"MiD2023_Comprehensive_Data.xlsx",english/"MiD2023_Comprehensive_Data_EN.xlsx"]:
        dest=target/source.name
        shutil.copyfile(source,dest)
        copied.append({"file":dest.relative_to(ROOT).as_posix(),"sha256":hashlib.sha256(dest.read_bytes()).hexdigest(),"bytes":dest.stat().st_size})
    entries={}
    def add(source, name):
        if source.is_file():
            entries[name]=source.read_bytes()
    add(comp/"intermediate/comprehensive_data.json","comprehensive/intermediate/comprehensive_data.json")
    for name in ["build_comprehensive.mjs","assemble_data.py","validate_export.py"]:
        add(comp/name,"comprehensive/"+name)
    for name in ["export_validation.json","workbook_manifest.json"]:
        add(comp/"intermediate"/name,"comprehensive/intermediate/"+name)
    for name in ["english_patches.json","prepare_patches.py","extract_inventory.py","sync_table_headers.py",
                 "english_validation.json","table_header_metadata_repair.json","string_catalogue.json",
                 "translations_context.json","translations_questionnaire.json","translations_codebook.json"]:
        add(english/name,"english/"+name)
    # Preserve the original builder; add an explicit environment override for portability.
    source=(english/"translate_workbook.mjs").read_text(encoding="utf-8")
    entries["english/translate_workbook.original.mjs"]=source.encode()
    source=source.replace("const hash=createHash", "if(process.env.MID_SOURCE_WORKBOOK)p.source_file=process.env.MID_SOURCE_WORKBOOK;\nconst hash=createHash")
    entries["english/translate_workbook.mjs"]=source.encode()
    for source in (comp/"mit_sources").glob("*.json"):
        # Raw source tables, original exact requests and response provenance.
        if source.name.startswith(("reise_","tage_","p_","w_","vars_","datasets","queries_","successful_","cohort_equivalence")):
            add(source,"public_mit_20261118/"+source.name)
    for source in (comp/"questionnaire").glob("*.py"):
        add(source,"questionnaire/"+source.name)
    for name in ["questions.json","answer_options.json","source_manifest.json","validation.json"]:
        add(comp/"questionnaire"/name,"questionnaire/"+name)
    for name in ["METHODS.md","SOURCE_INVENTORY.csv"]:
        add(first/name,"early_archive/"+name)
    for folder in [comp/"geography",comp/"airports",first/"sources",first/"muc_sources"]:
        for source in folder.glob("*manifest*.json"):
            add(source,"source_manifests/"+folder.name+"_"+source.name)
    entries["REBUILD.txt"]=(
        "Frozen inputs for the 27-sheet workbook created on 18 November 2026.\n"
        "The comprehensive builder reads only comprehensive/intermediate/comprehensive_data.json.\n"
        "Its assembly script documents the upstream raw sources; large original PDFs/XLSX are referenced by URLs/hashes, not duplicated here.\n"
        "To recreate the original layout, install @oai/artifact-tool, extract this archive, then run node comprehensive/build_comprehensive.mjs.\n"
        "To recreate the English translation, set MID_SOURCE_WORKBOOK to the absolute path of the frozen original workbook under data/workbooks.\n"
        "Then run node english/translate_workbook.mjs, followed by python english/sync_table_headers.py.\n"
        "The latter changes only native Excel table-header metadata, not worksheet values.\n"
        "Use the frozen original as translation input: rebuilt XLSX ZIP bytes may differ with runtime versions even if cell values match.\n"
        "All copied source/audit files retain their original bytes except the explicitly named portable translation builder.\n"
    ).encode()
    manifest=[{"path":name,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()} for name,data in sorted(entries.items())]
    entries["MANIFEST.json"]=json.dumps(manifest,indent=2).encode()
    archive=target/"workbook_provenance_20261118.zip"
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(entries.items()):
            z.writestr(name,data)
    audit={"workbooks":copied,"archive":{"file":archive.relative_to(ROOT).as_posix(),"sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),"bytes":archive.stat().st_size,"entries":len(entries)},
           "scope":"Original 27-sheet research archive includes labelled non-MiD context. Only public MiD cohort tables enter this paper. No B1 respondent records or hidden airport wishlist are included."}
    (target/"provenance_manifest.json").write_text(json.dumps(audit,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(audit,indent=2))


if __name__=="__main__":
    main()
