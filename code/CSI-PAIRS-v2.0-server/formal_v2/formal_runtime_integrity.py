from __future__ import annotations

import base64
import csv
import email.parser
import hashlib
import importlib.metadata
import json
from pathlib import Path, PurePosixPath
import re
import sysconfig
from typing import Iterable
import zipfile


WHEELHOUSE_NAME = "csi-pairs-reviewed-wheels"
WHEEL_MANIFEST_NAME = "csi-pairs-reviewed-wheel-manifest.json"
WHEEL_MANIFEST_SCHEMA = "csi-pairs-reviewed-wheel-closure-v1"


def _normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _urlsafe_sha256(path: Path) -> str:
    return base64.urlsafe_b64encode(
        bytes.fromhex(_sha256_file(path))
    ).rstrip(b"=").decode("ascii")


def _safe_archive_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise RuntimeError(f"reviewed wheel contains unsafe path: {value!r}")
    return path


def _read_metadata(archive: zipfile.ZipFile, member: str) -> tuple[str, str]:
    try:
        message = email.parser.BytesParser().parsebytes(archive.read(member))
    except (KeyError, OSError) as error:
        raise RuntimeError("reviewed wheel metadata cannot be read") from error
    name = message.get("Name")
    version = message.get("Version")
    if not name or not version:
        raise RuntimeError("reviewed wheel metadata omits Name or Version")
    return str(name), str(version)


def _installed_path(
    wheel_member: PurePosixPath,
    *,
    data_prefix: str,
    root_kind: str,
) -> tuple[str, PurePosixPath]:
    parts = wheel_member.parts
    if parts[0] != data_prefix:
        return root_kind, wheel_member
    if len(parts) < 3 or parts[1] not in {"purelib", "platlib"}:
        raise RuntimeError(
            "reviewed runtime wheel uses an unsupported .data installation scheme: "
            f"{wheel_member}"
        )
    return parts[1], PurePosixPath(*parts[2:])


def _inspect_reviewed_wheel(
    wheel: Path,
    locked_name: str,
    locked: dict[str, object],
    wheel_sha256: str,
) -> dict[str, object]:
    if not wheel.is_file() or wheel.is_symlink():
        raise RuntimeError(f"reviewed wheel is unsafe or missing: {wheel.name}")
    hashes = locked.get("hashes")
    if not isinstance(hashes, (list, tuple)) or wheel_sha256 not in hashes:
        raise RuntimeError(f"reviewed wheel hash is not locked: {wheel.name}")

    try:
        archive = zipfile.ZipFile(wheel)
    except (OSError, zipfile.BadZipFile) as error:
        raise RuntimeError(f"reviewed wheel is not a valid ZIP archive: {wheel.name}") from error
    with archive:
        members = [info for info in archive.infolist() if not info.is_dir()]
        names = [info.filename for info in members]
        if len(names) != len(set(names)):
            raise RuntimeError(f"reviewed wheel has duplicate members: {wheel.name}")
        safe_names = {_safe_archive_path(name): info for name, info in zip(names, members)}
        metadata_members = [
            path for path in safe_names if len(path.parts) == 2 and path.parts[-1] == "METADATA"
            and path.parts[-2].endswith(".dist-info")
        ]
        wheel_members = [
            path for path in safe_names if len(path.parts) == 2 and path.parts[-1] == "WHEEL"
            and path.parts[-2].endswith(".dist-info")
        ]
        record_members = [
            path for path in safe_names if len(path.parts) == 2 and path.parts[-1] == "RECORD"
            and path.parts[-2].endswith(".dist-info")
        ]
        if not (len(metadata_members) == len(wheel_members) == len(record_members) == 1):
            raise RuntimeError(f"reviewed wheel has no unique dist-info contract: {wheel.name}")
        metadata_member = metadata_members[0]
        wheel_member = wheel_members[0]
        record_member = record_members[0]
        dist_info = metadata_member.parts[-2]
        if wheel_member.parts[-2] != dist_info or record_member.parts[-2] != dist_info:
            raise RuntimeError(f"reviewed wheel dist-info members disagree: {wheel.name}")

        name, version = _read_metadata(archive, str(metadata_member))
        if (
            _normalize_distribution_name(name) != _normalize_distribution_name(locked_name)
            or version != locked.get("version")
        ):
            raise RuntimeError(f"reviewed wheel metadata does not match lock: {wheel.name}")
        wheel_text = archive.read(str(wheel_member)).decode("utf-8", errors="strict")
        root_matches = re.findall(r"(?im)^Root-Is-Purelib:\s*(true|false)\s*$", wheel_text)
        if len(root_matches) != 1:
            raise RuntimeError(f"reviewed wheel has invalid Root-Is-Purelib: {wheel.name}")
        root_kind = "purelib" if root_matches[0].lower() == "true" else "platlib"

        try:
            record_bytes = archive.read(str(record_member))
            rows = list(csv.reader(record_bytes.decode("utf-8").splitlines()))
        except (UnicodeError, csv.Error) as error:
            raise RuntimeError(f"reviewed wheel RECORD is invalid: {wheel.name}") from error
        record_paths: set[PurePosixPath] = set()
        installed_files: list[dict[str, object]] = []
        data_prefix = f"{dist_info[:-10]}.data"
        for row in rows:
            if len(row) != 3 or not row[0]:
                raise RuntimeError(f"reviewed wheel RECORD row is invalid: {wheel.name}")
            member = _safe_archive_path(row[0])
            if member in record_paths:
                raise RuntimeError(f"reviewed wheel RECORD has duplicate paths: {wheel.name}")
            record_paths.add(member)
            if member == record_member:
                if row[1:] != ["", ""]:
                    raise RuntimeError(f"reviewed wheel RECORD self-row is hashed: {wheel.name}")
                continue
            if member not in safe_names or not row[1].startswith("sha256=") or not row[2].isdigit():
                raise RuntimeError(f"reviewed wheel RECORD is incomplete: {wheel.name}")
            info = safe_names[member]
            if info.file_size != int(row[2]):
                raise RuntimeError(f"reviewed wheel RECORD size mismatch: {member}")
            encoded_hash = row[1].split("=", 1)[1]
            if re.fullmatch(r"[A-Za-z0-9_-]{43}", encoded_hash) is None:
                raise RuntimeError(f"reviewed wheel RECORD hash is invalid: {member}")
            install_root, relative = _installed_path(
                member,
                data_prefix=data_prefix,
                root_kind=root_kind,
            )
            if relative.suffix == ".pyc" or "__pycache__" in relative.parts:
                raise RuntimeError(f"reviewed wheel contains forbidden bytecode: {member}")
            if relative.name in {"sitecustomize.py", "usercustomize.py"}:
                raise RuntimeError(f"reviewed wheel contains a forbidden startup hook: {member}")
            installed_files.append(
                {
                    "root": install_root,
                    "path": str(relative),
                    "sha256_urlsafe": encoded_hash,
                    "size": int(row[2]),
                }
            )
        if record_paths != set(safe_names):
            raise RuntimeError(f"reviewed wheel RECORD does not cover the archive: {wheel.name}")

    return {
        "filename": wheel.name,
        "name": name,
        "normalized_name": _normalize_distribution_name(name),
        "version": version,
        "sha256": wheel_sha256,
        "dist_info": dist_info,
        "record_member": str(record_member),
        "record_sha256": hashlib.sha256(record_bytes).hexdigest(),
        "files": installed_files,
    }


def reviewed_wheel_manifest(
    wheelhouse: Path,
    expected: dict[str, dict[str, object]],
    requirements_lock_sha256: str,
) -> dict[str, object]:
    if not wheelhouse.is_dir() or wheelhouse.is_symlink():
        raise RuntimeError("reviewed wheelhouse is missing or unsafe")
    wheels = sorted(wheelhouse.iterdir(), key=lambda path: path.name)
    if not wheels or any(path.suffix.lower() != ".whl" for path in wheels):
        raise RuntimeError("reviewed wheelhouse must contain only wheel archives")
    expected_by_normalized = {
        _normalize_distribution_name(name): (name, record) for name, record in expected.items()
    }
    inspected: dict[str, dict[str, object]] = {}
    for wheel in wheels:
        digest = _sha256_file(wheel)
        candidates = [
            (name, record)
            for name, record in expected.items()
            if digest in record.get("hashes", ())
        ]
        if len(candidates) != 1:
            raise RuntimeError(f"reviewed wheel does not identify one locked package: {wheel.name}")
        name, record = candidates[0]
        normalized = _normalize_distribution_name(name)
        if normalized in inspected:
            raise RuntimeError(f"reviewed wheelhouse has duplicate package: {name}")
        inspected[normalized] = _inspect_reviewed_wheel(wheel, name, record, digest)
    if set(inspected) != set(expected_by_normalized):
        missing = sorted(set(expected_by_normalized).difference(inspected))
        unexpected = sorted(set(inspected).difference(expected_by_normalized))
        raise RuntimeError(
            f"reviewed wheelhouse inventory mismatch: missing={missing}, unexpected={unexpected}"
        )
    return {
        "schema_version": WHEEL_MANIFEST_SCHEMA,
        "requirements_lock_sha256": requirements_lock_sha256,
        "wheels": [inspected[name] for name in sorted(inspected)],
    }


def canonical_manifest_bytes(manifest: dict[str, object]) -> bytes:
    return (
        json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


def write_reviewed_wheel_manifest(
    wheelhouse: Path,
    output: Path,
    expected: dict[str, dict[str, object]],
    requirements_lock_sha256: str,
) -> dict[str, object]:
    manifest = reviewed_wheel_manifest(wheelhouse, expected, requirements_lock_sha256)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite reviewed wheel manifest: {output}")
    output.write_bytes(canonical_manifest_bytes(manifest))
    return manifest


def _default_site_roots(prefix: Path) -> dict[str, Path]:
    roots = {
        kind: Path(sysconfig.get_path(kind)).resolve() for kind in ("purelib", "platlib")
    }
    for kind, root in roots.items():
        if root != prefix and prefix not in root.parents:
            raise RuntimeError(f"main runtime {kind} path escapes interpreter prefix")
        if not root.is_dir() or root.is_symlink():
            raise RuntimeError(f"main runtime {kind} path is missing or unsafe")
    return roots


def validate_installed_wheel_closure(
    prefix: Path,
    wheelhouse: Path,
    manifest_path: Path,
    expected: dict[str, dict[str, object]],
    requirements_lock_sha256: str,
    *,
    site_roots: dict[str, Path] | None = None,
    observed_distribution_names: Iterable[str] | None = None,
) -> dict[str, object]:
    prefix = prefix.resolve()
    manifest = reviewed_wheel_manifest(wheelhouse, expected, requirements_lock_sha256)
    expected_manifest = canonical_manifest_bytes(manifest)
    if (
        not manifest_path.is_file()
        or manifest_path.is_symlink()
        or manifest_path.read_bytes() != expected_manifest
    ):
        raise RuntimeError("reviewed wheel manifest is missing or differs from locked wheels")
    roots = _default_site_roots(prefix) if site_roots is None else {
        kind: path.resolve() for kind, path in site_roots.items()
    }
    if set(roots) != {"purelib", "platlib"}:
        raise RuntimeError("main runtime site-package roots are incomplete")
    for root in roots.values():
        if root != prefix and prefix not in root.parents:
            raise RuntimeError("main runtime site-package root escapes interpreter prefix")

    expected_files: dict[Path, tuple[str, int, str]] = {}
    record_digests: dict[str, str] = {}
    for wheel in manifest["wheels"]:
        assert isinstance(wheel, dict)
        normalized = str(wheel["normalized_name"])
        for file_record in wheel["files"]:
            assert isinstance(file_record, dict)
            root = roots[str(file_record["root"])]
            candidate = (root / str(file_record["path"])).resolve()
            if candidate != root and root not in candidate.parents:
                raise RuntimeError("reviewed wheel installed path escapes site-packages")
            if candidate in expected_files:
                raise RuntimeError(f"reviewed wheels collide at installed path: {candidate}")
            expected_files[candidate] = (
                str(file_record["sha256_urlsafe"]),
                int(file_record["size"]),
                normalized,
            )
        dist_info = str(wheel["dist_info"])
        record_path = (roots["purelib"] / dist_info / "RECORD").resolve()
        if not record_path.exists() and roots["platlib"] != roots["purelib"]:
            record_path = (roots["platlib"] / dist_info / "RECORD").resolve()
        generated = {
            record_path: None,
            record_path.with_name("INSTALLER"): b"pip\n",
            record_path.with_name("REQUESTED"): b"",
        }
        for path, exact_content in generated.items():
            if not path.is_file() or path.is_symlink():
                raise RuntimeError(f"main runtime installer metadata is missing or unsafe: {path}")
            if exact_content is not None and path.read_bytes() != exact_content:
                raise RuntimeError(f"main runtime installer metadata differs: {path}")
            if path in expected_files:
                raise RuntimeError(f"main runtime generated metadata collides: {path}")
            expected_files[path] = (_urlsafe_sha256(path), path.stat().st_size, normalized)
        record_digests[normalized] = _sha256_file(record_path)

    actual_files: set[Path] = set()
    for root in set(roots.values()):
        for candidate in root.rglob("*"):
            if candidate.is_symlink():
                raise RuntimeError(f"main runtime site-packages contains a symlink: {candidate}")
            if not candidate.is_file():
                continue
            if candidate.suffix == ".pyc" or "__pycache__" in candidate.parts:
                raise RuntimeError(f"main runtime contains forbidden bytecode: {candidate}")
            if candidate.name in {"sitecustomize.py", "usercustomize.py"}:
                raise RuntimeError(f"main runtime contains a forbidden startup hook: {candidate}")
            actual_files.add(candidate.resolve())
    expected_paths = set(expected_files)
    if actual_files != expected_paths:
        missing = sorted(str(path) for path in expected_paths.difference(actual_files))
        unexpected = sorted(str(path) for path in actual_files.difference(expected_paths))
        raise RuntimeError(
            "main runtime installed-file closure mismatch: "
            f"missing={missing[:10]}, unexpected={unexpected[:10]}"
        )
    for path, (encoded_hash, size, _) in expected_files.items():
        if path.stat().st_size != size or _urlsafe_sha256(path) != encoded_hash:
            raise RuntimeError(f"main runtime file differs from reviewed wheel: {path}")

    if observed_distribution_names is None:
        observed_distribution_names = [
            distribution.metadata["Name"]
            for root in set(roots.values())
            for distribution in importlib.metadata.distributions(path=[str(root)])
        ]
    normalized_observed = [_normalize_distribution_name(name) for name in observed_distribution_names]
    expected_names = {_normalize_distribution_name(name) for name in expected}
    if len(normalized_observed) != len(set(normalized_observed)) or set(normalized_observed) != expected_names:
        raise RuntimeError(
            "main runtime installed-distribution closure mismatch: "
            f"expected={sorted(expected_names)}, observed={sorted(normalized_observed)}"
        )
    return {
        "manifest": manifest,
        "manifest_sha256": hashlib.sha256(expected_manifest).hexdigest(),
        "wheelhouse_sha256": hashlib.sha256(
            "\n".join(
                f"{wheel['sha256']}  {wheel['filename']}" for wheel in manifest["wheels"]
            ).encode("utf-8")
        ).hexdigest(),
        "record_digests": record_digests,
    }
