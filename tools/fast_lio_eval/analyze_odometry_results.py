#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import sqlite3
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


ODOM_TOPIC = "/Odometry"
ODOM_MSG = get_message("nav_msgs/msg/Odometry")
COLORS = {"github": "#2f7d32", "bitbucket": "#c62828"}
RESULT_DIR_ALIASES = {
    "github": ("github", "official"),
    "bitbucket": ("bitbucket",),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract /Odometry from github/bitbucket replay bags and plot trajectories."
    )
    parser.add_argument(
        "results_dir",
        help="Path like /home/rho/Documents/data/lio_eval/results/obstacle_approach",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory. Default: <results_dir>/analysis",
    )
    return parser.parse_args()


def find_db3_files(bag_dir: Path) -> list[Path]:
    db3_files = sorted(bag_dir.glob("*.db3"))
    if not db3_files:
        raise FileNotFoundError(f"No .db3 files found in {bag_dir}")
    return db3_files


def load_odometry_df(bag_dir: Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for db3_path in find_db3_files(bag_dir):
        conn = sqlite3.connect(str(db3_path))
        cur = conn.cursor()

        cur.execute("SELECT id FROM topics WHERE name = ?", (ODOM_TOPIC,))
        topic_row = cur.fetchone()
        if topic_row is None:
            conn.close()
            raise RuntimeError(f"{ODOM_TOPIC} not found in {db3_path}")
        topic_id = topic_row[0]

        cur.execute(
            "SELECT timestamp, data FROM messages WHERE topic_id = ? ORDER BY timestamp",
            (topic_id,),
        )
        for bag_timestamp_ns, raw_data in cur.fetchall():
            msg = deserialize_message(raw_data, ODOM_MSG)
            header_stamp_ns = msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec
            pose = msg.pose.pose
            rows.append(
                {
                    "bag_timestamp_ns": int(bag_timestamp_ns),
                    "header_stamp_ns": int(header_stamp_ns),
                    "frame_id": msg.header.frame_id,
                    "child_frame_id": msg.child_frame_id,
                    "x": float(pose.position.x),
                    "y": float(pose.position.y),
                    "z": float(pose.position.z),
                    "qx": float(pose.orientation.x),
                    "qy": float(pose.orientation.y),
                    "qz": float(pose.orientation.z),
                    "qw": float(pose.orientation.w),
                }
            )

        conn.close()

    if not rows:
        raise RuntimeError(f"No {ODOM_TOPIC} messages found in {bag_dir}")

    df = pd.DataFrame(rows).sort_values("bag_timestamp_ns").reset_index(drop=True)
    df["bag_time_s"] = (df["bag_timestamp_ns"] - df["bag_timestamp_ns"].iloc[0]) / 1e9
    df["header_time_s"] = (df["header_stamp_ns"] - df["header_stamp_ns"].iloc[0]) / 1e9

    for axis in ("x", "y", "z"):
        df[f"{axis}_rel"] = df[axis] - df[axis].iloc[0]

    return df


def compute_path_length(df: pd.DataFrame) -> float:
    dx = df["x_rel"].diff().fillna(0.0)
    dy = df["y_rel"].diff().fillna(0.0)
    dz = df["z_rel"].diff().fillna(0.0)
    return float((dx.pow(2) + dy.pow(2) + dz.pow(2)).pow(0.5).sum())


def display_label(label: str) -> str:
    return "GitHub" if label == "github" else "Bitbucket"


def resolve_output_bag_dir(results_dir: Path, label: str) -> Path | None:
    for dirname in RESULT_DIR_ALIASES[label]:
        bag_dir = results_dir / dirname / "out_topics"
        if bag_dir.is_dir():
            return bag_dir
    return None


def plot_single_xz(df: pd.DataFrame, label: str, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.plot(df["x_rel"], df["z_rel"], linewidth=1.5, label=label, color=COLORS.get(label))
    ax.scatter(df["x_rel"].iloc[0], df["z_rel"].iloc[0], marker="o", s=50, label="start")
    ax.scatter(df["x_rel"].iloc[-1], df["z_rel"].iloc[-1], marker="x", s=60, label="end")
    ax.set_title(f"{display_label(label)} XZ trajectory")
    ax.set_xlabel("x relative [m]")
    ax.set_ylabel("z relative [m]")
    ax.grid(True, alpha=0.3)
    ax.axis("equal")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def plot_compare_xz(data: dict[str, pd.DataFrame], output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 7))
    for label, df in data.items():
        ax.plot(df["x_rel"], df["z_rel"], linewidth=1.5, label=label, color=COLORS.get(label))
        ax.scatter(df["x_rel"].iloc[0], df["z_rel"].iloc[0], marker="o", s=30, color=COLORS.get(label))
        ax.scatter(df["x_rel"].iloc[-1], df["z_rel"].iloc[-1], marker="x", s=40, color=COLORS.get(label))
    ax.set_title("GitHub vs Bitbucket XZ trajectory")
    ax.set_xlabel("x relative [m]")
    ax.set_ylabel("z relative [m]")
    ax.grid(True, alpha=0.3)
    ax.axis("equal")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def plot_compare_z_time(data: dict[str, pd.DataFrame], output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.8))
    for label, df in data.items():
        ax.plot(
            df["header_time_s"],
            df["z_rel"],
            linewidth=1.5,
            label=label,
            color=COLORS.get(label),
        )
    ax.set_title("GitHub vs Bitbucket Z drift")
    ax.set_xlabel("relative time [s]")
    ax.set_ylabel("z relative [m]")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def write_summary(data: dict[str, pd.DataFrame], output_path: Path) -> None:
    lines = ["# Odometry Analysis Summary", ""]
    for label, df in data.items():
        duration_s = float(df["header_time_s"].iloc[-1]) if len(df) > 1 else 0.0
        sample_rate = (len(df) / duration_s) if duration_s > 0 else 0.0
        final_xz = math.hypot(float(df["x_rel"].iloc[-1]), float(df["z_rel"].iloc[-1]))
        max_abs_z = float(df["z_rel"].abs().max())
        max_abs_y = float(df["y_rel"].abs().max())
        path_length = compute_path_length(df)
        lines.extend(
            [
                f"## {label}",
                "",
                f"- samples: {len(df)}",
                f"- duration_s: {duration_s:.3f}",
                f"- sample_rate_hz: {sample_rate:.3f}",
                f"- path_length_m: {path_length:.3f}",
                f"- final_xz_offset_m: {final_xz:.3f}",
                f"- final_y_offset_m: {float(df['y_rel'].iloc[-1]):.3f}",
                f"- final_z_offset_m: {float(df['z_rel'].iloc[-1]):.3f}",
                f"- max_abs_y_rel_m: {max_abs_y:.3f}",
                f"- max_abs_z_rel_m: {max_abs_z:.3f}",
                "",
            ]
        )

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    results_dir = Path(args.results_dir).expanduser().resolve()
    if not results_dir.is_dir():
        print(f"Results directory not found: {results_dir}", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else results_dir / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    data: dict[str, pd.DataFrame] = {}
    for label in ("github", "bitbucket"):
        bag_dir = resolve_output_bag_dir(results_dir, label)
        if bag_dir is not None:
            df = load_odometry_df(bag_dir)
            csv_path = output_dir / f"{label}_odom.csv"
            df.to_csv(csv_path, index=False)
            plot_single_xz(df, label, output_dir / f"{label}_xz.png")
            data[label] = df
            print(f"[{label}] wrote {csv_path}")
        else:
            print(f"[{label}] skipped, replay bag not found under {results_dir}")

    if not data:
        print("No replay bags found to analyze.", file=sys.stderr)
        return 1

    if "github" in data and "bitbucket" in data:
        plot_compare_xz(data, output_dir / "github_vs_bitbucket_xz.png")
        plot_compare_z_time(data, output_dir / "github_vs_bitbucket_z_time.png")

    write_summary(data, output_dir / "summary.md")
    print(f"analysis output: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
