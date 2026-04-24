#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show github/bitbucket odometry trajectories in an interactive 3D window."
    )
    parser.add_argument(
        "analysis_dir",
        help="Path like /home/rho/Documents/data/lio_eval/results/obstacle_approach/analysis",
    )
    parser.add_argument(
        "--save",
        default=None,
        help="Optional path to save a 3D PNG snapshot.",
    )
    return parser.parse_args()


def load_csv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")
    return pd.read_csv(path)


def find_csv(analysis_dir: Path, candidates: list[str]) -> Path | None:
    for name in candidates:
        path = analysis_dir / name
        if path.is_file():
            return path
    return None


def plot_track(ax, df: pd.DataFrame, label: str, color: str) -> None:
    ax.plot(df["x_rel"], df["y_rel"], df["z_rel"], linewidth=1.5, label=label, color=color)
    ax.scatter(df["x_rel"].iloc[0], df["y_rel"].iloc[0], df["z_rel"].iloc[0], color=color, marker="o", s=45)
    ax.scatter(df["x_rel"].iloc[-1], df["y_rel"].iloc[-1], df["z_rel"].iloc[-1], color=color, marker="x", s=55)


def set_axes_equal_3d(ax) -> None:
    x_limits = ax.get_xlim3d()
    y_limits = ax.get_ylim3d()
    z_limits = ax.get_zlim3d()

    x_range = abs(x_limits[1] - x_limits[0])
    y_range = abs(y_limits[1] - y_limits[0])
    z_range = abs(z_limits[1] - z_limits[0])

    x_middle = sum(x_limits) / 2.0
    y_middle = sum(y_limits) / 2.0
    z_middle = sum(z_limits) / 2.0

    plot_radius = 0.5 * max(x_range, y_range, z_range)

    ax.set_xlim3d([x_middle - plot_radius, x_middle + plot_radius])
    ax.set_ylim3d([y_middle - plot_radius, y_middle + plot_radius])
    ax.set_zlim3d([z_middle - plot_radius, z_middle + plot_radius])


def main() -> int:
    args = parse_args()
    analysis_dir = Path(args.analysis_dir).expanduser().resolve()

    github_csv = find_csv(analysis_dir, ["github_odom.csv", "official_odom.csv"])
    bitbucket_csv = find_csv(analysis_dir, ["bitbucket_odom.csv"])

    github_df = load_csv(github_csv) if github_csv is not None else None
    bitbucket_df = load_csv(bitbucket_csv) if bitbucket_csv is not None else None

    if github_df is None and bitbucket_df is None:
        raise FileNotFoundError(f"No odometry CSVs found under {analysis_dir}")

    fig = plt.figure(figsize=(9, 7))
    ax = fig.add_subplot(111, projection="3d")

    if github_df is not None:
        plot_track(ax, github_df, "github", "#2f7d32")
    if bitbucket_df is not None:
        plot_track(ax, bitbucket_df, "bitbucket", "#c62828")

    ax.set_title("FAST-LIO odometry trajectories (3D)")
    ax.set_xlabel("x relative [m]")
    ax.set_ylabel("y relative [m]")
    ax.set_zlabel("z relative [m]")
    ax.legend()
    set_axes_equal_3d(ax)
    fig.tight_layout()

    if args.save:
        save_path = Path(args.save).expanduser().resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=180)
        print(f"saved snapshot: {save_path}")

    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
