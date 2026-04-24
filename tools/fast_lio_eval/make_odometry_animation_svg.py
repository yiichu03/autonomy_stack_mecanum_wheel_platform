#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an animated SVG from github/bitbucket odometry CSV files."
    )
    parser.add_argument(
        "analysis_dir",
        help="Path like /home/rho/Documents/data/lio_eval/results/obstacle_approach/analysis",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=12.0,
        help="Animation duration in seconds. Default: 12",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=240,
        help="Number of animation keyframes. Default: 240",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output SVG path. Default: <analysis_dir>/github_vs_bitbucket_xz_anim.svg",
    )
    return parser.parse_args()


def load_csv(path: Path) -> pd.DataFrame | None:
    if not path.is_file():
        return None
    return pd.read_csv(path)


def find_csv(analysis_dir: Path, candidates: list[str]) -> pd.DataFrame | None:
    for name in candidates:
        path = analysis_dir / name
        if path.is_file():
            return pd.read_csv(path)
    return None


def interp_series(df: pd.DataFrame, target_t: np.ndarray, column: str) -> np.ndarray:
    src_t = df["header_time_s"].to_numpy(dtype=float)
    src_v = df[column].to_numpy(dtype=float)
    if len(src_t) == 1:
        return np.full_like(target_t, src_v[0], dtype=float)
    return np.interp(target_t, src_t, src_v)


def map_x(value: float, min_v: float, max_v: float, left: float, width: float) -> float:
    if max_v == min_v:
      return left + width / 2.0
    return left + (value - min_v) / (max_v - min_v) * width


def map_y(value: float, min_v: float, max_v: float, top: float, height: float) -> float:
    if max_v == min_v:
      return top + height / 2.0
    return top + height - (value - min_v) / (max_v - min_v) * height


def polyline_points(df: pd.DataFrame, x_min: float, x_max: float, z_min: float, z_max: float,
                    left: float, top: float, plot_w: float, plot_h: float) -> str:
    pts = []
    for _, row in df.iterrows():
        x = map_x(float(row["x_rel"]), x_min, x_max, left, plot_w)
        y = map_y(float(row["z_rel"]), z_min, z_max, top, plot_h)
        pts.append(f"{x:.2f},{y:.2f}")
    return " ".join(pts)


def animated_values(values: np.ndarray, mapper) -> str:
    return ";".join(f"{mapper(v):.2f}" for v in values)


def main() -> int:
    args = parse_args()
    analysis_dir = Path(args.analysis_dir).expanduser().resolve()
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else analysis_dir / "github_vs_bitbucket_xz_anim.svg"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    github_df = find_csv(analysis_dir, ["github_odom.csv", "official_odom.csv"])
    bitbucket_df = find_csv(analysis_dir, ["bitbucket_odom.csv"])
    if github_df is None and bitbucket_df is None:
        raise FileNotFoundError(f"No odometry CSVs found under {analysis_dir}")

    all_dfs = [df for df in [github_df, bitbucket_df] if df is not None]
    x_all = pd.concat([df["x_rel"] for df in all_dfs], ignore_index=True)
    z_all = pd.concat([df["z_rel"] for df in all_dfs], ignore_index=True)

    x_min, x_max = float(x_all.min()), float(x_all.max())
    z_min, z_max = float(z_all.min()), float(z_all.max())
    x_pad = max((x_max - x_min) * 0.08, 0.5)
    z_pad = max((z_max - z_min) * 0.08, 0.5)
    x_min -= x_pad
    x_max += x_pad
    z_min -= z_pad
    z_max += z_pad

    max_t = max(float(df["header_time_s"].iloc[-1]) for df in all_dfs)
    target_t = np.linspace(0.0, max_t, args.frames)

    width = 1080
    height = 760
    left = 110
    top = 60
    plot_w = 840
    plot_h = 560
    duration = max(args.duration, 0.1)

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{left}" y="30" font-size="28" font-family="monospace" fill="#111">GitHub vs Bitbucket XZ trajectory animation</text>',
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#fafafa" stroke="#333" stroke-width="1.5"/>',
    ]

    for i in range(6):
        frac = i / 5.0
        gx = left + frac * plot_w
        gy = top + frac * plot_h
        svg_parts.append(f'<line x1="{gx:.2f}" y1="{top}" x2="{gx:.2f}" y2="{top+plot_h}" stroke="#e0e0e0" stroke-width="1"/>')
        svg_parts.append(f'<line x1="{left}" y1="{gy:.2f}" x2="{left+plot_w}" y2="{gy:.2f}" stroke="#e0e0e0" stroke-width="1"/>')

    svg_parts.extend([
        f'<text x="{left + plot_w/2:.1f}" y="{top + plot_h + 55}" text-anchor="middle" font-size="24" font-family="monospace">x relative [m]</text>',
        f'<text x="30" y="{top + plot_h/2:.1f}" text-anchor="middle" font-size="24" font-family="monospace" transform="rotate(-90 30 {top + plot_h/2:.1f})">z relative [m]</text>',
    ])

    legend_y = top + plot_h + 95
    svg_parts.append(f'<rect x="{left}" y="{legend_y-22}" width="20" height="8" fill="#2f7d32"/>')
    svg_parts.append(f'<text x="{left+30}" y="{legend_y-12}" font-size="22" font-family="monospace">github</text>')
    svg_parts.append(f'<rect x="{left+170}" y="{legend_y-22}" width="20" height="8" fill="#c62828"/>')
    svg_parts.append(f'<text x="{left+200}" y="{legend_y-12}" font-size="22" font-family="monospace">bitbucket</text>')

    colors = {"github": "#2f7d32", "bitbucket": "#c62828"}
    dfs = {"github": github_df, "bitbucket": bitbucket_df}
    for label, df in dfs.items():
        if df is None:
            continue
        points = polyline_points(df, x_min, x_max, z_min, z_max, left, top, plot_w, plot_h)
        svg_parts.append(
            f'<polyline fill="none" stroke="{colors[label]}" stroke-width="2.3" opacity="0.55" points="{points}"/>'
        )

        x_interp = interp_series(df, target_t, "x_rel")
        z_interp = interp_series(df, target_t, "z_rel")
        cx_values = animated_values(x_interp, lambda v: map_x(float(v), x_min, x_max, left, plot_w))
        cy_values = animated_values(z_interp, lambda v: map_y(float(v), z_min, z_max, top, plot_h))

        start_x = map_x(float(df["x_rel"].iloc[0]), x_min, x_max, left, plot_w)
        start_y = map_y(float(df["z_rel"].iloc[0]), z_min, z_max, top, plot_h)
        end_x = map_x(float(df["x_rel"].iloc[-1]), x_min, x_max, left, plot_w)
        end_y = map_y(float(df["z_rel"].iloc[-1]), z_min, z_max, top, plot_h)
        svg_parts.append(f'<circle cx="{start_x:.2f}" cy="{start_y:.2f}" r="5" fill="{colors[label]}" opacity="0.8"/>')
        svg_parts.append(f'<line x1="{end_x-5:.2f}" y1="{end_y-5:.2f}" x2="{end_x+5:.2f}" y2="{end_y+5:.2f}" stroke="{colors[label]}" stroke-width="2.5"/>')
        svg_parts.append(f'<line x1="{end_x-5:.2f}" y1="{end_y+5:.2f}" x2="{end_x+5:.2f}" y2="{end_y-5:.2f}" stroke="{colors[label]}" stroke-width="2.5"/>')

        svg_parts.append(
            f'<circle id="{label}_dot" cx="{start_x:.2f}" cy="{start_y:.2f}" r="8" fill="{colors[label]}" stroke="#111" stroke-width="1.2">'
            f'<animate attributeName="cx" values="{cx_values}" dur="{duration:.2f}s" repeatCount="indefinite"/>'
            f'<animate attributeName="cy" values="{cy_values}" dur="{duration:.2f}s" repeatCount="indefinite"/>'
            f'</circle>'
        )

    svg_parts.append("</svg>")
    output_path.write_text("\n".join(svg_parts), encoding="utf-8")
    print(f"wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
