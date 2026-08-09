#!/usr/bin/env python3
"""B1 Stage 1: generate the per-target MCP wheelhouse and hashed lock.

Runs (or consumes the output of) `pip download mcp==2.0.0 --only-binary=:all:`
natively on a target machine, then:

- rejects any non-.whl file (no sdist fallback is permitted),
- parses each wheel's name/version from its filename and cross-checks METADATA,
- computes the SHA-256 of every wheel,
- writes requirements-cp314-macos-<arch>.lock with one
  `name==version --hash=sha256:<hex>` line per distribution (sorted,
  mcp==2.0.0 pinned, every transitive dependency pinned ==),
- writes WHEELHOUSE_MANIFEST.json as release evidence (never fed to pip).

Any sdist, unparsable wheel, duplicate distribution, or empty download
aborts without writing outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

PACKAGE = "mcp"
PIN = "2.0.0"
PYTHON_TAG = "cp314"

_WHEEL_FILENAME = re.compile(r"^(?P<name>[A-Za-z0-9_.]+)-(?P<version>[^-]+)-[^-]+-[^-]+-[^-]+\.whl$")


class WheelhouseError(RuntimeError):
    """Wheelhouse generation failed; no outputs may be written."""


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _wheel_identity(path: Path) -> tuple[str, str]:
    match = _WHEEL_FILENAME.match(path.name)
    if not match:
        raise WheelhouseError(f"Unparsable wheel filename: {path.name}")
    file_name = _normalize(match.group("name"))
    file_version = match.group("version")
    try:
        with zipfile.ZipFile(path) as archive:
            metadata_names = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
            if len(metadata_names) != 1:
                raise WheelhouseError(f"Wheel has no unique dist-info METADATA: {path.name}")
            metadata = archive.read(metadata_names[0]).decode("utf-8")
    except zipfile.BadZipFile as exc:
        raise WheelhouseError(f"Unreadable wheel archive: {path.name}") from exc
    fields: dict[str, str] = {}
    for line in metadata.splitlines():
        if line.startswith(("Name:", "Version:")):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    if _normalize(fields.get("Name", "")) != file_name or fields.get("Version") != file_version:
        raise WheelhouseError(
            f"Wheel filename/METADATA identity mismatch: {path.name} "
            f"(METADATA Name={fields.get('Name')!r} Version={fields.get('Version')!r})"
        )
    return file_name, file_version


def finalize(wheelhouse: Path, *, arch: str) -> dict:
    """Validate a downloaded wheelhouse and write the lock + manifest."""
    files = sorted(path for path in wheelhouse.iterdir() if path.is_file())
    if not files:
        raise WheelhouseError(f"Wheelhouse directory is empty: {wheelhouse}")
    entries: list[dict] = []
    seen: dict[str, str] = {}
    for path in files:
        if path.suffix != ".whl":
            if path.name == "WHEELHOUSE_MANIFEST.json" or (
                path.name.startswith("requirements-") and path.suffix == ".lock"
            ):
                continue  # this script's own prior outputs; re-runs are idempotent
            raise WheelhouseError(f"Non-wheel artifact in wheelhouse (sdist fallback is forbidden): {path.name}")
        name, version = _wheel_identity(path)
        if name in seen:
            raise WheelhouseError(f"Duplicate distribution in wheelhouse: {name} ({seen[name]}, {version})")
        seen[name] = version
        blob = path.read_bytes()
        entries.append(
            {
                "filename": path.name,
                "size": len(blob),
                "sha256": hashlib.sha256(blob).hexdigest(),
                "name": name,
                "version": version,
            }
        )
    if seen.get(PACKAGE) != PIN:
        raise WheelhouseError(f"Wheelhouse must contain exactly {PACKAGE}=={PIN}; found {seen.get(PACKAGE)!r}")

    # All validation passed; only now write outputs.
    lock_lines = [
        f"{entry['name']}=={entry['version']} --hash=sha256:{entry['sha256']}" for entry in entries
    ]
    lock_path = wheelhouse / f"requirements-{PYTHON_TAG}-macos-{arch}.lock"
    manifest = {
        "schemaVersion": 1,
        "package": f"{PACKAGE}=={PIN}",
        "targetTriple": f"{PYTHON_TAG}-macos-{arch}",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "interpreter": {
            "executable": sys.executable,
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "wheels": entries,
    }
    manifest_path = wheelhouse / "WHEELHOUSE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lock_path.write_text("\n".join(lock_lines) + "\n", encoding="utf-8")
    return {"lock": lock_path, "manifest": manifest_path, "wheels": entries}


# --- Deterministic multi-architecture merge (Audit 9 release contract) ---
#
# Merging per-target wheelhouses must be a pure function of the inputs: no
# timestamps, no host identity, sorted output. The same two reviewed
# wheelhouses always produce byte-identical merged locks and manifests.

_WHEEL_PLATFORMS = re.compile(
    r"^(?P<name>[A-Za-z0-9_.]+)-(?P<version>[^-]+)-(?P<pytag>[^-]+)-(?P<abi>[^-]+)-(?P<platform>[^-]+)\.whl$"
)


def _wheel_platform_tags(filename: str) -> tuple[str, ...]:
    match = _WHEEL_PLATFORMS.match(filename)
    if not match:
        raise WheelhouseError(f"Unparsable wheel filename: {filename}")
    return tuple(match.group("platform").split("."))


def _wheel_supports_arch(filename: str, arch: str) -> bool:
    for tag in _wheel_platform_tags(filename):
        if tag == "any":
            return True
        if "macosx" in tag:
            if arch in tag or "universal2" in tag:
                return True
    return False


def merge_wheelhouses(inputs: list[tuple[Path, str]], output: Path) -> dict:
    """Merge reviewed per-target wheelhouses into one deterministic release
    input. Requires EXACTLY one reviewed arm64 input and one reviewed x86_64
    input; each input manifest's target triple must match its declared
    architecture (mislabeled and single-architecture merges are rejected).
    Every distribution must appear in every input at the SAME version;
    per-target merged locks carry one == pin with one --hash per
    target-compatible wheel (pure wheels are shared; arch-specific wheels are
    selected by platform tag). Aborts on any version conflict, filename/hash
    disagreement, unknown architecture, or non-wheel content."""
    architectures = sorted({arch for _path, arch in inputs})
    if architectures != ["arm64", "x86_64"]:
        raise WheelhouseError(
            f"Merge requires exactly one reviewed arm64 input and one reviewed x86_64 input; "
            f"got architectures: {architectures}"
        )
    if len(inputs) != len(architectures):
        raise WheelhouseError("Merge requires exactly one wheelhouse per architecture.")

    # distribution -> {"version": str, "wheels": {filename: {"sha256", "arches"}}}
    merged: dict[str, dict] = {}
    per_arch_distributions: dict[str, dict[str, str]] = {}  # arch -> {name: version}
    for wheelhouse, arch in inputs:
        manifest_path = wheelhouse / "WHEELHOUSE_MANIFEST.json"
        if not manifest_path.is_file():
            raise WheelhouseError(f"Merge input is not a finalized wheelhouse: {wheelhouse}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_triple = f"{PYTHON_TAG}-macos-{arch}"
        if manifest.get("targetTriple") != expected_triple:
            raise WheelhouseError(
                f"Merge input target triple {manifest.get('targetTriple')!r} does not match its "
                f"declared architecture {arch!r} (expected {expected_triple!r}): {wheelhouse}"
            )
        arch_distributions: dict[str, str] = {}
        for entry in sorted(manifest.get("wheels", []), key=lambda item: item["filename"]):
            wheel = wheelhouse / entry["filename"]
            if not wheel.is_file():
                raise WheelhouseError(f"Manifest wheel is missing from its wheelhouse: {entry['filename']}")
            blob = wheel.read_bytes()
            if hashlib.sha256(blob).hexdigest() != entry["sha256"]:
                raise WheelhouseError(f"Wheel hash diverges from its wheelhouse manifest: {entry['filename']}")
            slot = merged.setdefault(entry["name"], {"version": entry["version"], "wheels": {}})
            if slot["version"] != entry["version"]:
                raise WheelhouseError(
                    f"Version conflict for {entry['name']}: {slot['version']} vs {entry['version']} across targets"
                )
            known = slot["wheels"].setdefault(entry["filename"], {"sha256": entry["sha256"], "arches": []})
            if known["sha256"] != entry["sha256"]:
                raise WheelhouseError(f"Same wheel filename with different hashes across targets: {entry['filename']}")
            known["arches"].append(arch)
            arch_distributions[entry["name"]] = entry["version"]
        per_arch_distributions[arch] = arch_distributions

    # R6-06: identical normalized distribution-name/version sets across both
    # reviewed target manifests.  A distribution missing from one target, a
    # version difference, or a pure/universal wheel present in only one
    # manifest all fail closed.
    if len(per_arch_distributions) != 2:
        raise WheelhouseError("Merge requires exactly one reviewed arm64 manifest and one reviewed x86_64 manifest.")
    arch_names = sorted(per_arch_distributions)
    first_arch, second_arch = arch_names[0], arch_names[1]
    first_set = per_arch_distributions[first_arch]
    second_set = per_arch_distributions[second_arch]
    if set(first_set) != set(second_set):
        only_first = sorted(set(first_set) - set(second_set))
        only_second = sorted(set(second_set) - set(first_set))
        raise WheelhouseError(
            f"Distribution sets differ across targets: only in {first_arch}: {only_first}; "
            f"only in {second_arch}: {only_second}"
        )
    for name in sorted(first_set):
        if first_set[name] != second_set[name]:
            raise WheelhouseError(
                f"Version conflict for {name} across targets: {first_arch}={first_set[name]} vs "
                f"{second_arch}={second_set[name]}"
            )
    # A pure/universal wheel must appear in BOTH reviewed target manifests.
    for name, slot in sorted(merged.items()):
        for filename, info in sorted(slot["wheels"].items()):
            if _wheel_supports_arch(filename, "arm64") and _wheel_supports_arch(filename, "x86_64"):
                if set(info["arches"]) != {"arm64", "x86_64"}:
                    raise WheelhouseError(
                        f"Pure/universal wheel {filename} appears in only one reviewed target manifest: "
                        f"{sorted(info['arches'])}"
                    )

    if merged.get(PACKAGE, {}).get("version") != PIN:
        raise WheelhouseError(f"Merged wheelhouse must contain exactly {PACKAGE}=={PIN}")

    output.mkdir(parents=True, exist_ok=True)
    all_files = sorted({filename for slot in merged.values() for filename in slot["wheels"]})
    for filename in all_files:
        for wheelhouse, _arch in inputs:
            candidate = wheelhouse / filename
            if candidate.is_file():
                target = output / filename
                blob = candidate.read_bytes()
                if target.exists() and target.read_bytes() != blob:
                    raise WheelhouseError(f"Output wheel collision with different content: {filename}")
                target.write_bytes(blob)
                break

    locks: dict[str, Path] = {}
    for arch in architectures:
        lines = []
        for name in sorted(merged):
            slot = merged[name]
            hashes = sorted(
                {
                    info["sha256"]
                    for filename, info in slot["wheels"].items()
                    if _wheel_supports_arch(filename, arch)
                }
            )
            if not hashes:
                raise WheelhouseError(f"No {arch}-compatible wheel for distribution: {name}")
            lines.append(f"{name}=={slot['version']}" + "".join(f" --hash=sha256:{digest}" for digest in hashes))
        lock_path = output / f"requirements-{PYTHON_TAG}-macos-{arch}.lock"
        lock_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        locks[arch] = lock_path

    manifest = {
        "schemaVersion": 1,
        "kind": "merged-wheelhouse",
        "package": f"{PACKAGE}=={PIN}",
        "architectures": architectures,
        "deterministic": True,
        "distributions": {
            name: {
                "version": merged[name]["version"],
                "wheels": {
                    filename: {
                        "sha256": merged[name]["wheels"][filename]["sha256"],
                        "arches": sorted(merged[name]["wheels"][filename]["arches"]),
                    }
                    for filename in sorted(merged[name]["wheels"])
                },
            }
            for name in sorted(merged)
        },
    }
    manifest_path = output / "MERGED_WHEELHOUSE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"locks": locks, "manifest": manifest_path, "distributions": sorted(merged)}


def download(wheelhouse: Path, *, python: str, pins: list[str] | None = None) -> None:
    command = [
        python,
        "-m",
        "pip",
        "download",
        f"{PACKAGE}=={PIN}",
        "--only-binary=:all:",
        "--no-cache-dir",
        "--dest",
        str(wheelhouse),
    ]
    for pin in pins or []:
        command.append(pin)
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise WheelhouseError(f"pip download failed with exit code {completed.returncode}")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["merge"]:
        merge_parser = argparse.ArgumentParser(description="Deterministically merge per-target wheelhouses.")
        merge_parser.add_argument(
            "--input", action="append", required=True, metavar="WHEELHOUSE:ARCH",
            help="Reviewed per-target wheelhouse with its architecture (repeatable).",
        )
        merge_parser.add_argument("--output", required=True, type=Path, help="Merged output directory (fresh).")
        merge_args = merge_parser.parse_args(argv[1:])
        try:
            inputs = []
            for spec in merge_args.input:
                path_text, separator, arch = spec.rpartition(":")
                if not separator or not path_text:
                    raise WheelhouseError(f"Merge input must be WHEELHOUSE:ARCH: {spec!r}")
                inputs.append((Path(path_text), arch))
            result = merge_wheelhouses(inputs, merge_args.output)
        except WheelhouseError as exc:
            print(f"wheelhouse merge aborted: {exc}", file=sys.stderr)
            return 2
        for arch in sorted(result["locks"]):
            print(result["locks"][arch])
        print(result["manifest"])
        print(f"wheelhouse merge sealed: {len(result['distributions'])} distributions, deterministic")
        return 0

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheelhouse", required=True, type=Path, help="Fresh wheelhouse directory")
    parser.add_argument("--arch", required=True, choices=("arm64", "x86_64"), help="Native target architecture")
    parser.add_argument("--python", default=sys.executable, help="Target CPython 3.14 interpreter for pip download")
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Skip pip download; finalize an already-populated wheelhouse directory",
    )
    parser.add_argument(
        "--pin",
        action="append",
        default=[],
        metavar="SPEC",
        help="Extra pip requirement pin (repeatable) applied during download, e.g. cryptography==50.0.0",
    )
    args = parser.parse_args(argv)
    try:
        args.wheelhouse.mkdir(parents=True, exist_ok=True)
        if not args.no_download:
            download(args.wheelhouse, python=args.python, pins=args.pin)
        result = finalize(args.wheelhouse, arch=args.arch)
    except WheelhouseError as exc:
        print(f"wheelhouse generation aborted: {exc}", file=sys.stderr)
        return 2
    print(result["lock"])
    print(result["manifest"])
    print(f"wheelhouse sealed: {len(result['wheels'])} wheels for cp314-macos-{args.arch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
