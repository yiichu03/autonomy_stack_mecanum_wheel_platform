#!/usr/bin/env python3
"""
Export a leveled gravity log from FAST-LIO's raw pos_log.txt.

This converts the raw FAST-LIO gravity vector into the same leveled ROS map
frame used by the Scout launch files:
  q_total = q_level * q_map_camera_init

The output is a CSV plus a short summary text file under runtime_logs.
"""

from __future__ import annotations

import argparse
import csv
import math
from datetime import datetime
from pathlib import Path


Q_MAP_CAMERA_INIT = (-0.5, 0.5, -0.5, 0.5)
DEFAULT_Q_LEVEL = (-0.004276, 0.043092, 0.0, 0.999062)


def normalize_quat(q):
    x, y, z, w = q
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if norm < 1e-12:
        return (0.0, 0.0, 0.0, 1.0)
    return (x / norm, y / norm, z / norm, w / norm)


def quat_multiply(q1, q2):
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q2
    return (
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
    )


def quat_conjugate(q):
    x, y, z, w = q
    return (-x, -y, -z, w)


def rotate_vector(q, v):
    qv = (v[0], v[1], v[2], 0.0)
    qr = quat_multiply(quat_multiply(q, qv), quat_conjugate(q))
    return (qr[0], qr[1], qr[2])


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[4]


def default_input_path() -> Path:
    return Path("/home/rho/Documents/liuyi/projects/thermal_nav/fastlio_ws/src/FAST_LIO/Log/pos_log.txt")


def default_output_dir() -> Path:
    return (
        workspace_root()
        / "runtime_logs"
        / "gravity_level_check"
        / datetime.now().strftime("%Y%m%d_%H%M%S")
    )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(default_input_path()), help="FAST-LIO pos_log.txt path")
    parser.add_argument("--output-dir", default=str(default_output_dir()), help="Output directory")
    parser.add_argument("--qx", type=float, default=DEFAULT_Q_LEVEL[0], help="Leveling quaternion x")
    parser.add_argument("--qy", type=float, default=DEFAULT_Q_LEVEL[1], help="Leveling quaternion y")
    parser.add_argument("--qz", type=float, default=DEFAULT_Q_LEVEL[2], help="Leveling quaternion z")
    parser.add_argument("--qw", type=float, default=DEFAULT_Q_LEVEL[3], help="Leveling quaternion w")
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(f"input log not found: {input_path}")

    q_level = normalize_quat((args.qx, args.qy, args.qz, args.qw))
    q_total = normalize_quat(quat_multiply(q_level, Q_MAP_CAMERA_INIT))

    csv_path = output_dir / "leveled_gravity.csv"
    summary_path = output_dir / "summary.txt"

    rows = 0
    sum_fx = sum_fy = sum_fz = 0.0
    sum_rx = sum_ry = sum_rz = 0.0

    with input_path.open("r", encoding="utf-8") as f_in, csv_path.open(
        "w", encoding="utf-8", newline=""
    ) as f_out:
        writer = csv.writer(f_out)
        writer.writerow([
            "time",
            "grav_fast_x",
            "grav_fast_y",
            "grav_fast_z",
            "grav_leveled_x",
            "grav_leveled_y",
            "grav_leveled_z",
            "grav_norm",
            "grav_horiz",
            "tilt_deg",
        ])

        for line in f_in:
            parts = line.strip().split()
            if len(parts) < 25:
                continue

            t = float(parts[0])
            fx, fy, fz = map(float, parts[-3:])
            rx, ry, rz = rotate_vector(q_total, (fx, fy, fz))
            norm = math.sqrt(rx * rx + ry * ry + rz * rz)
            horiz = math.sqrt(rx * rx + ry * ry)
            tilt_deg = math.degrees(math.atan2(horiz, abs(rz)))

            writer.writerow([
                f"{t:.6f}",
                f"{fx:.6f}",
                f"{fy:.6f}",
                f"{fz:.6f}",
                f"{rx:.6f}",
                f"{ry:.6f}",
                f"{rz:.6f}",
                f"{norm:.6f}",
                f"{horiz:.6f}",
                f"{tilt_deg:.6f}",
            ])

            rows += 1
            sum_fx += fx
            sum_fy += fy
            sum_fz += fz
            sum_rx += rx
            sum_ry += ry
            sum_rz += rz

    if rows == 0:
        raise RuntimeError(f"no valid rows found in {input_path}")

    mean_fx = sum_fx / rows
    mean_fy = sum_fy / rows
    mean_fz = sum_fz / rows
    mean_rx = sum_rx / rows
    mean_ry = sum_ry / rows
    mean_rz = sum_rz / rows
    mean_norm = math.sqrt(mean_rx * mean_rx + mean_ry * mean_ry + mean_rz * mean_rz)
    mean_horiz = math.sqrt(mean_rx * mean_rx + mean_ry * mean_ry)
    mean_tilt_deg = math.degrees(math.atan2(mean_horiz, abs(mean_rz)))

    with summary_path.open("w", encoding="utf-8") as f:
        f.write(f"input={input_path}\n")
        f.write(f"rows={rows}\n")
        f.write(
            "q_level=[%.6f, %.6f, %.6f, %.6f]\n"
            % (q_level[0], q_level[1], q_level[2], q_level[3])
        )
        f.write(
            "q_total=[%.6f, %.6f, %.6f, %.6f]\n"
            % (q_total[0], q_total[1], q_total[2], q_total[3])
        )
        f.write(
            "grav_fastlio_mean=[%.6f, %.6f, %.6f]\n"
            % (mean_fx, mean_fy, mean_fz)
        )
        f.write(
            "grav_leveled_mean=[%.6f, %.6f, %.6f]\n"
            % (mean_rx, mean_ry, mean_rz)
        )
        f.write(f"grav_leveled_norm={mean_norm:.6f}\n")
        f.write(f"grav_leveled_horiz={mean_horiz:.6f}\n")
        f.write(f"grav_leveled_tilt_deg={mean_tilt_deg:.6f}\n")

    print(f"wrote {csv_path}")
    print(f"wrote {summary_path}")
    print(
        "grav_leveled_mean=[%.6f, %.6f, %.6f], horiz=%.6f, tilt_deg=%.3f"
        % (mean_rx, mean_ry, mean_rz, mean_horiz, mean_tilt_deg)
    )


if __name__ == "__main__":
    main()
