"""Compare the supplied 02/03 ZIPs, their published copies and old run manifests.

Reads archive members as data; executes no uploaded Python. Usage:
python audit_source_zips.py --zip02 PATH --zip03 PATH --published-dir DIR
--manifest02 PATH --manifest03 PATH --output PATH
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inspect(upload, published, result_manifest):
    with zipfile.ZipFile(upload) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failure")
        names = [n for n in archive.namelist() if not n.endswith("/")]
        if len(names) != len(set(names)):
            raise ValueError("duplicate ZIP path")
        prefix = names[0].split("/", 1)[0] + "/"
        if not all(n.startswith(prefix) for n in names):
            raise ValueError("multiple package roots")
        data = {n[len(prefix):]: archive.read(n) for n in names}
    manifest = json.loads(data["SOURCE_MANIFEST.json"])
    verification = json.loads(data["VERIFICATION.json"])
    mismatches = [n for n, digest in manifest["files_sha256"].items()
                  if n not in data or sha(data[n]) != digest]
    core = [n for n in data if n.startswith("hotpotqa_operadic_rag/") and n.endswith(".py")]
    code_hashes = {}
    for platform, ordering in [("posix", PurePosixPath), ("windows_path_sort", PureWindowsPath)]:
        h = hashlib.sha256()
        for name in ["decomposition_pilot.py", *sorted(core, key=ordering)]:
            h.update(name.encode())
            h.update(data[name])
        code_hashes[platform] = h.hexdigest()
    recorded = json.loads(result_manifest.read_text(encoding="utf-8"))["settings"]["code_sha256"]
    return {"filename": upload.name, "bytes": upload.stat().st_size, "sha256": sha(upload.read_bytes()),
            "equals_published_zip_byte_for_byte": upload.read_bytes() == published.read_bytes(),
            "immutable_release_commit": "eb304676fb44c17ddcb64be217b652a1540f7276",
            "manifest_entries_checked": len(manifest["files_sha256"]), "manifest_mismatches": mismatches,
            "code_files_hashed": len(core) + 1, "code_hashes": code_hashes,
            "internal_verification_code_sha256": verification["source_code_sha256"],
            "verification_matches_computed_code": verification["source_code_sha256"] == code_hashes["posix"],
            "old_result_manifest_code_sha256": recorded,
            "runtime_hash_equals_uploaded_code": recorded == code_hashes["posix"],
            "per_file_code_sha256": {n: sha(data[n]) for n in sorted(["decomposition_pilot.py", *core])}}


def main():
    parser = argparse.ArgumentParser()
    for option in ["zip02", "zip03", "published-dir", "manifest02", "manifest03", "output"]:
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args()
    result = {}
    for number in ["02", "03"]:
        path = getattr(args, "zip" + number)
        result[number] = inspect(path, args.published_dir / path.name, getattr(args, "manifest" + number))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: {k: v for k, v in value.items() if k != "per_file_code_sha256"}
                      for key, value in result.items()}, ensure_ascii=False, indent=2))
    if any(not x["equals_published_zip_byte_for_byte"] or x["manifest_mismatches"] or
           not x["verification_matches_computed_code"] for x in result.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
