#!/usr/bin/env python3
"""Independently verify formal HOTA_NEW_HERO_V1.06."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from build_hota_new_hero_v1 import extract_zip_safely, safe_recreate_directory
import build_hota_new_hero_v106 as release
import build_hota_new_hero_v106_ui_test2 as test2
from verify_hota_new_hero_v106_ui_test2 import files, verify_dll


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--candidate-zip", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_zip = args.source_zip.resolve()
    candidate_zip = args.candidate_zip.resolve()
    manifest_path = args.manifest.resolve()
    work_root = args.work_root.resolve()
    if test2.sha256_file(source_zip) != test2.SOURCE_ZIP_SHA256:
        raise RuntimeError("Formal V1.05 ZIP hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["build_name"] != release.BUILD_NAME or not manifest["formal_release"]:
        raise RuntimeError("Formal manifest identity mismatch")
    if manifest["zip_sha256"] != test2.sha256_file(candidate_zip):
        raise RuntimeError("Candidate ZIP hash does not match manifest")
    if manifest["accepted_test_zip_sha256"] != release.ACCEPTED_TEST_ZIP_SHA256:
        raise RuntimeError("Accepted UI_TEST2 identity mismatch")
    with zipfile.ZipFile(candidate_zip, "r") as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise RuntimeError(f"Candidate ZIP CRC failure: {bad_member}")

    safe_recreate_directory(work_root, work_root.parent)
    source_root = work_root / "source"
    candidate_root = work_root / "candidate"
    source_root.mkdir()
    candidate_root.mkdir()
    extract_zip_safely(source_zip, source_root)
    extract_zip_safely(candidate_zip, candidate_root)
    source_files = files(source_root)
    candidate_files = files(candidate_root)
    if set(source_files) != set(candidate_files):
        raise RuntimeError("Candidate member set differs from formal V1.05")

    root_texts = [name for name in source_files if "/" not in name and name.lower().endswith(".txt")]
    if len(root_texts) != 1:
        raise RuntimeError("Expected one root installation text")
    changed = {
        name for name in source_files
        if test2.sha256_file(source_files[name]) != test2.sha256_file(candidate_files[name])
    }
    allowed = {test2.HOTA_DLL_NAME, root_texts[0]}
    if changed != allowed:
        raise RuntimeError(f"Unexpected package changes: {sorted(changed)}")

    test2.validate_formula_helpers(candidate_root)
    dll_report = verify_dll(
        source_files[test2.HOTA_DLL_NAME],
        candidate_files[test2.HOTA_DLL_NAME],
    )
    if dll_report["sha256"] != release.ACCEPTED_HOTA_DLL_SHA256:
        raise RuntimeError("Formal HotA.dll differs from accepted UI_TEST2 runtime payload")
    install_text = candidate_files[root_texts[0]].read_text(encoding="utf-8")
    if release.BUILD_NAME not in install_text or "40-60" not in install_text:
        raise RuntimeError("Formal installation text identity/acceptance details missing")

    print(json.dumps({
        "verified": True,
        "formal_release": release.BUILD_NAME,
        "candidate_zip_sha256": test2.sha256_file(candidate_zip),
        "changed_files": sorted(changed),
        "accepted_runtime_payload_match": True,
        "hota_dll": dll_report,
    }, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
