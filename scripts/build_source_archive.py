#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
# SPDX-License-Identifier: Apache-2.0
"""Build a deterministic, source-only TrackB release archive."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import stat
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".git",
    ".lake",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "receipts",
}
EXCLUDED_SUFFIXES = {
    ".a",
    ".bc",
    ".c",
    ".ilean",
    ".o",
    ".olean",
    ".pyc",
    ".so",
}


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def is_release_source(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if path.name == ".DS_Store" or path.suffix in EXCLUDED_SUFFIXES:
        return False
    return True


def collect_sources() -> list[Path]:
    sources: list[Path] = []
    for path in ROOT.rglob("*"):
        if not is_release_source(path):
            continue
        if path.is_symlink():
            raise SystemExit(f"source archive rejects symlink: {path}")
        if path.is_file():
            relative = PurePosixPath(path.relative_to(ROOT).as_posix())
            if relative.is_absolute() or ".." in relative.parts:
                raise SystemExit(f"unsafe source archive path: {relative}")
            sources.append(path)
    return sorted(sources, key=lambda path: path.relative_to(ROOT).as_posix())


def source_mode(path: Path) -> int:
    return 0o755 if path.stat().st_mode & stat.S_IXUSR else 0o644


def make_manifest(sources: list[Path], prefix: str) -> dict[str, object]:
    files = []
    for path in sources:
        raw = path.read_bytes()
        files.append(
            {
                "mode": f"{source_mode(path):04o}",
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size": len(raw),
            }
        )
    return {
        "schema_version": "trackb-source-archive-manifest-v1",
        "archive_prefix": prefix,
        "file_count": len(files),
        "files": files,
    }


def build_tar(sources: list[Path], prefix: str) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path in sources:
            raw = path.read_bytes()
            relative = path.relative_to(ROOT).as_posix()
            info = tarfile.TarInfo(name=f"{prefix}/{relative}")
            info.size = len(raw)
            info.mode = source_mode(path)
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            archive.addfile(info, io.BytesIO(raw))
    return buffer.getvalue()


def gzip_deterministically(raw_tar: bytes) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(
        filename="",
        mode="wb",
        fileobj=buffer,
        compresslevel=9,
        mtime=0,
    ) as compressed:
        compressed.write(raw_tar)
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    parser.add_argument(
        "--prefix",
        default="trackb-lean-replay-checker-v0.2.1",
    )
    arguments = parser.parse_args()

    if (
        not arguments.prefix
        or arguments.prefix.startswith("/")
        or ".." in PurePosixPath(arguments.prefix).parts
    ):
        raise SystemExit("archive prefix must be a safe relative path")

    if arguments.output.is_symlink() or arguments.manifest_output.is_symlink():
        raise SystemExit("source archive outputs must not be symlinks")
    output = arguments.output.resolve()
    manifest_output = arguments.manifest_output.resolve()
    if output == manifest_output:
        raise SystemExit(
            "archive and manifest outputs must be distinct paths"
        )
    for target in (output, manifest_output):
        if target == ROOT or ROOT in target.parents:
            raise SystemExit("release archive outputs must be outside the source tree")

    sources = collect_sources()
    manifest = make_manifest(sources, arguments.prefix)
    raw_manifest = canonical_json_bytes(manifest)
    raw_archive = gzip_deterministically(
        build_tar(sources, arguments.prefix)
    )
    atomic_write(output, raw_archive)
    atomic_write(manifest_output, raw_manifest)

    print(
        json.dumps(
            {
                "archive": str(output),
                "archive_sha256": hashlib.sha256(raw_archive).hexdigest(),
                "file_count": len(sources),
                "manifest": str(manifest_output),
                "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
                "result": "PASS",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
