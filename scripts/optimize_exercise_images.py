from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd
from PIL import Image, ImageOps


APP_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = APP_DIR / "assets" / "exercises"
OPTIMIZED_DIR = ASSETS_DIR / "optimized"
THUMB_DIR = ASSETS_DIR / "thumbnails"
REPORT_DIR = APP_DIR / "reports"
REPORT_PATH = REPORT_DIR / "exercise_image_optimization_report.csv"


def _source_images() -> List[Path]:
    files: List[Path] = []
    for ext in ("*.png", "*.jpg", "*.jpeg"):
        files.extend(ASSETS_DIR.glob(ext))
    return sorted([path for path in files if path.is_file()])


def _webp_output_name(source: Path) -> str:
    return f"{source.stem}.webp"


def _thumb_output_name(source: Path) -> str:
    return f"{source.stem}_thumb.webp"


def _optimize_one(source: Path) -> Dict[str, object]:
    optimized_path = OPTIMIZED_DIR / _webp_output_name(source)
    thumb_path = THUMB_DIR / _thumb_output_name(source)

    with Image.open(source) as img:
        image = ImageOps.exif_transpose(img.convert("RGB"))

        image.save(optimized_path, format="WEBP", quality=84, method=6)

        thumb = image.copy()
        thumb.thumbnail((480, 480))
        thumb.save(thumb_path, format="WEBP", quality=78, method=6)

    src_bytes = source.stat().st_size
    webp_bytes = optimized_path.stat().st_size
    thumb_bytes = thumb_path.stat().st_size
    savings = max(src_bytes - webp_bytes, 0)

    return {
        "source_path": str(source.relative_to(APP_DIR)),
        "optimized_path": str(optimized_path.relative_to(APP_DIR)),
        "thumbnail_path": str(thumb_path.relative_to(APP_DIR)),
        "source_kb": round(src_bytes / 1024.0, 2),
        "optimized_kb": round(webp_bytes / 1024.0, 2),
        "thumbnail_kb": round(thumb_bytes / 1024.0, 2),
        "savings_kb": round(savings / 1024.0, 2),
        "savings_percent": round((savings / src_bytes) * 100.0, 2) if src_bytes else 0.0,
    }


def _estimate_reduction_kb(source: Path) -> float:
    # Conservative pre-conversion estimate for PNG/JPG to WebP.
    src_kb = source.stat().st_size / 1024.0
    return round(src_kb * 0.55, 2)


def main() -> None:
    OPTIMIZED_DIR.mkdir(parents=True, exist_ok=True)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    source_files = _source_images()
    estimated_total_saved_kb = sum(_estimate_reduction_kb(path) for path in source_files)
    print(f"Estimated reduction before conversion: {estimated_total_saved_kb:.2f} KB")

    rows: List[Dict[str, object]] = []
    for source in source_files:
        try:
            rows.append(_optimize_one(source))
        except Exception as exc:
            rows.append(
                {
                    "source_path": str(source.relative_to(APP_DIR)),
                    "optimized_path": "",
                    "thumbnail_path": "",
                    "source_kb": round(source.stat().st_size / 1024.0, 2),
                    "optimized_kb": 0.0,
                    "thumbnail_kb": 0.0,
                    "savings_kb": 0.0,
                    "savings_percent": 0.0,
                    "error": str(exc),
                }
            )

    report = pd.DataFrame(rows)
    report.to_csv(REPORT_PATH, index=False)

    total_before = float(report.get("source_kb", pd.Series(dtype=float)).fillna(0).sum())
    total_after = float(report.get("optimized_kb", pd.Series(dtype=float)).fillna(0).sum())
    total_saved = max(total_before - total_after, 0.0)

    print(f"Optimized {len(report)} images")
    print(f"Total source size: {total_before:.2f} KB")
    print(f"Total optimized size: {total_after:.2f} KB")
    print(f"Total saved: {total_saved:.2f} KB")
    print(f"Report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
