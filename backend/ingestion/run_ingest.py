import json
import sys
from pathlib import Path

from backend.ingestion.normalizers import sha256_file
from backend.ingestion.pipeline import ingest_paths, write_outputs

ROOT = Path(__file__).resolve().parents[2]


def verify_manifest(indir: Path):
    m = indir / "SHA256SUMS.txt"
    if not m.exists():
        return
    bad = []
    for line in m.read_text().splitlines():
        digest, fn = line.split("  ", 1)
        if not (indir / fn).exists() or sha256_file(str(indir / fn)) != digest:
            bad.append(fn)
    print("Manifest check:", "ALL FILES MATCH" if not bad else f"MISMATCH -> {bad}")


def main():
    indir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "synthetic"
    outdir = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "data" / "canonical"
    verify_manifest(indir)
    out = ingest_paths(sorted(str(p) for p in indir.iterdir() if p.is_file()))
    write_outputs(out, str(outdir))
    print(json.dumps(out.summary, indent=2))
    print(f"\nCanonical output -> {outdir}")


if __name__ == "__main__":
    main()
