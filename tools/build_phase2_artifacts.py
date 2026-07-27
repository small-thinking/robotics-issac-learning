#!/usr/bin/env python3
"""Build compact Phase 2 datasets and dependency-free SVG figures."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import shutil
import statistics
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

VARIANT_ORDER = [
    "B0",
    "O_POS",
    "O_H4",
    "R_CV0",
    "R_CV2",
    "A_E50",
    "A_E200",
    "T_B15",
    "T_B60",
]
VARIANT_LABELS = {
    "B0": "Baseline",
    "O_POS": "Position only",
    "O_H4": "4-frame history",
    "R_CV0": "Cart-vel 0",
    "R_CV2": "Cart-vel -0.02",
    "A_E50": "Effort 50",
    "A_E200": "Effort 200",
    "T_B15": "Bound 1.5",
    "T_B60": "Bound 6.0",
}
FACTOR_COLORS = {
    "baseline": "#334155",
    "observation": "#2563eb",
    "reward": "#d97706",
    "action": "#db2777",
    "termination": "#6b8e23",
}
METRICS = [
    "robust_success_fraction",
    "mean_upright_fraction_12deg",
    "mean_longest_upright_seconds",
    "mean_pole_angle_rms_radians",
    "mean_cart_position_rms",
    "mean_max_abs_cart_position",
    "mean_abs_cart_velocity",
    "mean_pole_angular_velocity_rms",
    "mean_abs_normalized_action",
    "mean_abs_requested_effort",
    "mean_abs_action_delta",
    "mean_action_total_variation",
    "mean_action_sign_changes_per_second",
    "mean_action_saturation_fraction",
    "time_limit_fraction",
]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _artifact(manifest: dict[str, Any], kind: str) -> dict[str, Any]:
    return next(item for item in manifest["artifacts"] if item["kind"] == kind)


def load_study(source: Path) -> dict[str, Any]:
    manifests = [_read_json(path) for path in sorted((source / "manifests").glob("*.json"))]
    if len(manifests) != 27:
        raise ValueError(f"expected 27 manifests, found {len(manifests)}")
    if any(manifest["status"] != "succeeded" for manifest in manifests):
        raise ValueError("every formal manifest must be succeeded")

    checkpoint_identity: dict[str, tuple[str, int]] = {}
    for manifest in manifests:
        checkpoint = _artifact(manifest, "primary_checkpoint")["path_or_uri"]
        checkpoint_identity[checkpoint] = (
            manifest["variant"]["id"],
            int(manifest["training"]["seed"]),
        )

    screening = {
        path.stem: _read_json(path)
        for path in sorted((source / "evaluations" / "screening").glob("*.json"))
    }
    final = {
        path.stem: _read_json(path)
        for path in sorted((source / "evaluations" / "final").glob("*.json"))
    }
    if set(screening) != set(VARIANT_ORDER) or set(final) != set(VARIANT_ORDER):
        raise ValueError("screening and final evaluation files must cover all variants")
    return {
        "manifests": manifests,
        "checkpoint_identity": checkpoint_identity,
        "screening": screening,
        "final": final,
        "study_summary": _read_json(source / "study_summary.json"),
    }


def derive_rows(study: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    manifests = study["manifests"]
    checkpoint_identity = study["checkpoint_identity"]
    manifest_by_identity = {
        (manifest["variant"]["id"], int(manifest["training"]["seed"])): manifest
        for manifest in manifests
    }

    registry_rows: list[dict[str, Any]] = []
    for manifest in manifests:
        primary = _artifact(manifest, "primary_checkpoint")
        train_command = next(
            (command for command in manifest["commands"] if command["stage"].startswith("train_")),
            None,
        )
        registry_rows.append(
            {
                "run_id": manifest["run_id"],
                "variant_id": manifest["variant"]["id"],
                "factor": manifest["variant"]["factor"],
                "factor_level": manifest["variant"]["factor_level"],
                "contrast_variant_id": manifest["variant"]["contrast_variant_id"] or "",
                "training_seed": manifest["training"]["seed"],
                "status": manifest["status"],
                "git_commit": manifest["provenance"]["git_commit"],
                "registry_sha256": manifest["variant"]["registry_sha256"],
                "checkpoint": primary["path_or_uri"],
                "checkpoint_sha256": primary["sha256"],
                "training_wall_seconds": (
                    "" if train_command is None else train_command["wall_seconds"]
                ),
            }
        )
    registry_rows.sort(
        key=lambda row: (VARIANT_ORDER.index(str(row["variant_id"])), int(row["training_seed"]))
    )

    curve_rows: list[dict[str, Any]] = []
    for variant_id in VARIANT_ORDER:
        evaluations = study["screening"][variant_id]["evaluations"]
        if len(evaluations) != 10:
            raise ValueError(f"{variant_id} screening must contain 10 checkpoints")
        for evaluation in evaluations:
            curve_rows.append(
                {
                    "variant_id": variant_id,
                    "variant_label": VARIANT_LABELS[variant_id],
                    "checkpoint_vector_steps": evaluation["checkpoint_vector_steps"],
                    "training_transitions": evaluation["training_transitions"],
                    "mean_balance_seconds": evaluation["mean_balance_seconds"],
                    "robust_success_fraction": evaluation["robust_success_fraction"],
                    "mean_upright_fraction_12deg": evaluation["mean_upright_fraction_12deg"],
                    "mean_pole_angle_rms_radians": evaluation["mean_pole_angle_rms_radians"],
                    "time_limit_fraction": evaluation["time_limit_fraction"],
                }
            )

    run_rows: list[dict[str, Any]] = []
    episode_rows: list[dict[str, Any]] = []
    for variant_id in VARIANT_ORDER:
        for evaluation in study["final"][variant_id]["evaluations"]:
            identity = checkpoint_identity.get(evaluation["checkpoint"])
            if identity is None or identity[0] != variant_id:
                raise ValueError(f"unmapped final checkpoint: {evaluation['checkpoint']}")
            training_seed = identity[1]
            manifest = manifest_by_identity[(variant_id, training_seed)]
            row: dict[str, Any] = {
                "run_id": manifest["run_id"],
                "variant_id": variant_id,
                "variant_label": VARIANT_LABELS[variant_id],
                "factor": manifest["variant"]["factor"],
                "factor_level": manifest["variant"]["factor_level"],
                "contrast_variant_id": manifest["variant"]["contrast_variant_id"] or "",
                "training_seed": training_seed,
                "episode_count": evaluation["episode_count"],
            }
            row.update({metric: evaluation[metric] for metric in METRICS})
            run_rows.append(row)

            for episode in evaluation["episodes"]:
                episode_row = {
                    "run_id": manifest["run_id"],
                    "variant_id": variant_id,
                    "training_seed": training_seed,
                    "evaluation_seed": episode["seed"],
                    "environment_id": episode["environment_id"],
                    "length_steps": episode["length"],
                    "termination_reason": episode["termination_reason"],
                    "robust_success": episode["robust_success"],
                }
                for key, value in episode.items():
                    if key not in {
                        "seed",
                        "environment_id",
                        "length",
                        "termination_reason",
                        "robust_success",
                        "reward",
                    }:
                        episode_row[key] = value
                episode_rows.append(episode_row)
    run_rows.sort(
        key=lambda row: (VARIANT_ORDER.index(str(row["variant_id"])), int(row["training_seed"]))
    )
    episode_rows.sort(
        key=lambda row: (
            VARIANT_ORDER.index(str(row["variant_id"])),
            int(row["training_seed"]),
            int(row["environment_id"]),
        )
    )

    run_by_identity = {(str(row["variant_id"]), int(row["training_seed"])): row for row in run_rows}
    paired_rows: list[dict[str, Any]] = []
    for row in run_rows:
        contrast = str(row["contrast_variant_id"])
        if not contrast:
            continue
        baseline = run_by_identity[(contrast, int(row["training_seed"]))]
        paired = {
            "variant_id": row["variant_id"],
            "contrast_variant_id": contrast,
            "training_seed": row["training_seed"],
        }
        for metric in METRICS:
            paired[f"delta_{metric}"] = float(row[metric]) - float(baseline[metric])
        paired_rows.append(paired)

    summary_rows: list[dict[str, Any]] = []
    for variant_id in VARIANT_ORDER:
        members = [row for row in run_rows if row["variant_id"] == variant_id]
        first = members[0]
        summary: dict[str, Any] = {
            "variant_id": variant_id,
            "variant_label": VARIANT_LABELS[variant_id],
            "factor": first["factor"],
            "factor_level": first["factor_level"],
            "n_training_seeds": len(members),
        }
        for metric in METRICS:
            values = [float(row[metric]) for row in members]
            summary[f"{metric}_mean"] = statistics.fmean(values)
            summary[f"{metric}_sd"] = statistics.stdev(values)
        summary_rows.append(summary)

    failure_rows: list[dict[str, Any]] = []
    for variant_id in VARIANT_ORDER:
        reasons = Counter(
            row["termination_reason"] for row in episode_rows if row["variant_id"] == variant_id
        )
        total = sum(reasons.values())
        for reason in sorted(reasons):
            failure_rows.append(
                {
                    "variant_id": variant_id,
                    "termination_reason": reason,
                    "episode_count": reasons[reason],
                    "fraction": reasons[reason] / total,
                }
            )

    return {
        "run_registry": registry_rows,
        "training_curves": curve_rows,
        "run_metrics": run_rows,
        "episode_metrics": episode_rows,
        "paired_effects": paired_rows,
        "condition_summary": summary_rows,
        "failure_composition": failure_rows,
    }


def _escape(value: Any) -> str:
    return html.escape(str(value))


def _svg_text(x: float, y: float, value: Any, **attrs: Any) -> str:
    attributes = " ".join(
        f'{key.replace("_", "-")}="{_escape(attr)}"' for key, attr in attrs.items()
    )
    return f'<text x="{x:.1f}" y="{y:.1f}" {attributes}>{_escape(value)}</text>'


def _svg_line(x1: float, y1: float, x2: float, y2: float, **attrs: Any) -> str:
    attributes = " ".join(
        f'{key.replace("_", "-")}="{_escape(attr)}"' for key, attr in attrs.items()
    )
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" {attributes}/>'


def _svg_header(width: int, height: int, title: str, subtitle: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#f8fafc"/>',
        _svg_text(
            48,
            43,
            title,
            font_family="system-ui, sans-serif",
            font_size="24",
            font_weight="700",
            fill="#102a43",
        ),
        _svg_text(
            48,
            68,
            subtitle,
            font_family="system-ui, sans-serif",
            font_size="14",
            fill="#486581",
        ),
    ]


def _polyline(points: Iterable[tuple[float, float]], color: str, width: float = 2.4) -> str:
    encoded = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return (
        f'<polyline points="{encoded}" fill="none" stroke="{color}" '
        f'stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>'
    )


def render_learning_dynamics(rows: list[dict[str, Any]]) -> str:
    width, height = 1180, 790
    elements = _svg_header(
        width,
        height,
        "CartPole learning dynamics",
        "Seed 42 screening; 25 fixed episodes per checkpoint; upright fraction over 5 seconds",
    )
    panel_w, panel_h = 330.0, 170.0
    x_gap, y_gap = 45.0, 55.0
    start_x, start_y = 70.0, 105.0
    for index, variant_id in enumerate(VARIANT_ORDER):
        col, row_index = index % 3, index // 3
        left = start_x + col * (panel_w + x_gap)
        top = start_y + row_index * (panel_h + y_gap)
        bottom = top + panel_h
        values = [item for item in rows if item["variant_id"] == variant_id]
        x_max = max(float(item["training_transitions"]) for item in values)
        for tick in range(3):
            fraction = tick / 2
            y = bottom - panel_h * fraction
            elements.append(
                _svg_line(left, y, left + panel_w, y, stroke="#d9e2ec", stroke_width="1")
            )
            elements.append(
                _svg_text(
                    left - 9,
                    y + 4,
                    f"{fraction:.0%}",
                    text_anchor="end",
                    font_size="11",
                    fill="#627d98",
                )
            )
        points = [
            (
                left + panel_w * float(item["training_transitions"]) / x_max,
                bottom - panel_h * float(item["mean_upright_fraction_12deg"]),
            )
            for item in values
        ]
        factor = (
            next(
                item["factor"]
                for item in rows
                if item["variant_id"] == variant_id and "factor" in item
            )
            if any("factor" in item for item in rows if item["variant_id"] == variant_id)
            else (
                "baseline"
                if variant_id == "B0"
                else (
                    "observation"
                    if variant_id.startswith("O_")
                    else (
                        "reward"
                        if variant_id.startswith("R_")
                        else ("action" if variant_id.startswith("A_") else "termination")
                    )
                )
            )
        )
        color = FACTOR_COLORS[factor]
        elements.append(_polyline(points, color))
        for x, y in points:
            elements.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{color}"/>')
        elements.append(
            _svg_text(
                left,
                top - 12,
                f"{variant_id} · {VARIANT_LABELS[variant_id]}",
                font_size="14",
                font_weight="650",
                fill="#243b53",
            )
        )
        elements.append(
            _svg_text(
                left + panel_w / 2,
                bottom + 23,
                "Training transitions → 9.83M",
                text_anchor="middle",
                font_size="11",
                fill="#627d98",
            )
        )
    elements.append("</svg>")
    return "\n".join(elements) + "\n"


def render_final_performance(rows: list[dict[str, Any]]) -> str:
    width, height = 1180, 650
    elements = _svg_header(
        width,
        height,
        "Final 30-second control performance",
        "Three PPO seeds; filled dots are means, whiskers ± SD, open dots trained policies",
    )
    panels = [
        ("robust_success_fraction", "Robust success", 1.0, lambda value: f"{value:.0%}"),
        (
            "mean_upright_fraction_12deg",
            "Upright fraction",
            1.0,
            lambda value: f"{value:.0%}",
        ),
        (
            "mean_pole_angle_rms_radians",
            "Pole-angle RMS",
            max(float(row["mean_pole_angle_rms_radians"]) for row in rows) * 1.15,
            lambda value: f"{math.degrees(value):.1f}°",
        ),
    ]
    panel_w, panel_h, gap = 330.0, 430.0, 48.0
    start_x, top = 70.0, 125.0
    jitter = [-8.0, 0.0, 8.0]
    for panel_index, (metric, label, y_max, formatter) in enumerate(panels):
        left = start_x + panel_index * (panel_w + gap)
        bottom = top + panel_h
        for tick in range(5):
            value = y_max * tick / 4
            y = bottom - panel_h * value / y_max
            elements.append(
                _svg_line(left, y, left + panel_w, y, stroke="#d9e2ec", stroke_width="1")
            )
            elements.append(
                _svg_text(
                    left - 8,
                    y + 4,
                    formatter(value),
                    text_anchor="end",
                    font_size="11",
                    fill="#627d98",
                )
            )
        step = panel_w / len(VARIANT_ORDER)
        for variant_index, variant_id in enumerate(VARIANT_ORDER):
            values = [float(row[metric]) for row in rows if row["variant_id"] == variant_id]
            mean = statistics.fmean(values)
            sd = statistics.stdev(values)
            x = left + step * (variant_index + 0.5)
            factor = next(row["factor"] for row in rows if row["variant_id"] == variant_id)
            color = FACTOR_COLORS[str(factor)]
            y_mean = bottom - panel_h * mean / y_max
            y_low = bottom - panel_h * max(0.0, mean - sd) / y_max
            y_high = bottom - panel_h * min(y_max, mean + sd) / y_max
            elements.append(_svg_line(x, y_low, x, y_high, stroke="#334e68", stroke_width="1.5"))
            elements.append(
                _svg_line(x - 5, y_low, x + 5, y_low, stroke="#334e68", stroke_width="1.5")
            )
            elements.append(
                _svg_line(x - 5, y_high, x + 5, y_high, stroke="#334e68", stroke_width="1.5")
            )
            elements.append(f'<circle cx="{x:.1f}" cy="{y_mean:.1f}" r="5.5" fill="{color}"/>')
            for point_index, value in enumerate(values):
                y = bottom - panel_h * value / y_max
                elements.append(
                    f'<circle cx="{x + jitter[point_index]:.1f}" cy="{y:.1f}" r="2.5" '
                    f'fill="#ffffff" stroke="{color}" stroke-width="1.5"/>'
                )
            elements.append(
                _svg_text(
                    x,
                    bottom + 15,
                    variant_id,
                    text_anchor="end",
                    font_size="10",
                    fill="#486581",
                    transform=f"rotate(-55 {x:.1f} {bottom + 15:.1f})",
                )
            )
        elements.append(
            _svg_text(
                left,
                top - 17,
                label,
                font_size="15",
                font_weight="650",
                fill="#243b53",
            )
        )
    elements.append("</svg>")
    return "\n".join(elements) + "\n"


def render_sensitivity(rows: list[dict[str, Any]]) -> str:
    width, height = 1180, 620
    elements = _svg_header(
        width,
        height,
        "One-factor control sensitivity",
        "Mean across three training seeds; lines connect only the three preregistered levels",
    )
    panels = [
        (
            "reward",
            [("R_CV2", -0.02), ("B0", -0.01), ("R_CV0", 0.0)],
            "Cart-velocity reward weight",
        ),
        ("action", [("A_E50", 50.0), ("B0", 100.0), ("A_E200", 200.0)], "Effort scale"),
        ("termination", [("T_B15", 1.5), ("B0", 3.0), ("T_B60", 6.0)], "Training bound magnitude"),
    ]
    metrics = [
        ("robust_success_fraction", "Robust success", "#2563eb"),
        ("mean_upright_fraction_12deg", "Upright fraction", "#d97706"),
    ]
    panel_w, panel_h, gap = 330.0, 360.0, 50.0
    start_x, top = 70.0, 125.0
    for panel_index, (factor, levels, x_label) in enumerate(panels):
        left = start_x + panel_index * (panel_w + gap)
        bottom = top + panel_h
        x_values = [value for _, value in levels]
        x_min, x_max = min(x_values), max(x_values)
        for tick in range(5):
            value = tick / 4
            y = bottom - panel_h * value
            elements.append(
                _svg_line(left, y, left + panel_w, y, stroke="#d9e2ec", stroke_width="1")
            )
            elements.append(
                _svg_text(
                    left - 8,
                    y + 4,
                    f"{value:.0%}",
                    text_anchor="end",
                    font_size="11",
                    fill="#627d98",
                )
            )
        for metric, metric_label, color in metrics:
            points: list[tuple[float, float]] = []
            for variant_id, level in levels:
                values = [float(row[metric]) for row in rows if row["variant_id"] == variant_id]
                mean = statistics.fmean(values)
                x = left + panel_w * (level - x_min) / (x_max - x_min)
                y = bottom - panel_h * mean
                points.append((x, y))
            elements.append(_polyline(points, color, 2.6))
            for x, y in points:
                elements.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{color}"/>')
        for variant_id, level in levels:
            x = left + panel_w * (level - x_min) / (x_max - x_min)
            elements.append(
                _svg_text(
                    x,
                    bottom + 20,
                    f"{level:g}",
                    text_anchor="middle",
                    font_size="11",
                    fill="#486581",
                )
            )
            elements.append(
                _svg_text(
                    x,
                    bottom + 37,
                    variant_id,
                    text_anchor="middle",
                    font_size="10",
                    fill="#829ab1",
                )
            )
        elements.append(
            _svg_text(
                left,
                top - 18,
                factor.title(),
                font_size="15",
                font_weight="650",
                fill="#243b53",
            )
        )
        elements.append(
            _svg_text(
                left + panel_w / 2,
                bottom + 58,
                x_label,
                text_anchor="middle",
                font_size="12",
                fill="#486581",
            )
        )
    elements.extend(
        [
            _svg_line(765, 91, 790, 91, stroke="#2563eb", stroke_width="3"),
            _svg_text(798, 95, "Robust success", font_size="12", fill="#486581"),
            _svg_line(930, 91, 955, 91, stroke="#d97706", stroke_width="3"),
            _svg_text(963, 95, "Upright fraction", font_size="12", fill="#486581"),
        ]
    )
    elements.append("</svg>")
    return "\n".join(elements) + "\n"


def render_control_sensitivity(rows: list[dict[str, Any]]) -> str:
    width, height = 1180, 620
    elements = _svg_header(
        width,
        height,
        "Control-style sensitivity",
        "Three PPO seeds per level; filled dots are means and open dots are trained policies",
    )
    panels = [
        (
            [("R_CV2", -0.02), ("B0", -0.01), ("R_CV0", 0.0)],
            "Reward",
            "Cart-velocity reward weight",
            "mean_abs_cart_velocity",
            "Mean absolute cart velocity",
            lambda value: f"{value:.2f}",
        ),
        (
            [("A_E50", 50.0), ("B0", 100.0), ("A_E200", 200.0)],
            "Action",
            "Effort scale",
            "mean_abs_requested_effort",
            "Mean absolute requested effort",
            lambda value: f"{value:.1f}",
        ),
        (
            [("T_B15", 1.5), ("B0", 3.0), ("T_B60", 6.0)],
            "Termination",
            "Training bound magnitude",
            "mean_cart_position_rms",
            "Cart-position RMS",
            lambda value: f"{value:.1f}",
        ),
    ]
    panel_w, panel_h, gap = 330.0, 360.0, 50.0
    start_x, top = 70.0, 125.0
    jitter = [-7.0, 0.0, 7.0]
    for panel_index, (levels, title, x_label, metric, y_label, formatter) in enumerate(panels):
        left = start_x + panel_index * (panel_w + gap)
        bottom = top + panel_h
        x_values = [level for _, level in levels]
        x_min, x_max = min(x_values), max(x_values)
        all_values = [
            float(row[metric])
            for variant_id, _ in levels
            for row in rows
            if row["variant_id"] == variant_id
        ]
        y_max = max(all_values) * 1.08
        for tick in range(5):
            value = y_max * tick / 4
            y = bottom - panel_h * tick / 4
            elements.append(
                _svg_line(left, y, left + panel_w, y, stroke="#d9e2ec", stroke_width="1")
            )
            elements.append(
                _svg_text(
                    left - 8,
                    y + 4,
                    formatter(value),
                    text_anchor="end",
                    font_size="11",
                    fill="#627d98",
                )
            )
        color = FACTOR_COLORS[title.lower()]
        points = []
        for variant_id, level in levels:
            values = [float(row[metric]) for row in rows if row["variant_id"] == variant_id]
            mean = statistics.fmean(values)
            x = left + panel_w * (level - x_min) / (x_max - x_min)
            y = bottom - panel_h * mean / y_max
            points.append((x, y))
            for point_index, value in enumerate(values):
                point_y = bottom - panel_h * value / y_max
                elements.append(
                    f'<circle cx="{x + jitter[point_index]:.1f}" cy="{point_y:.1f}" '
                    f'r="3" fill="#ffffff" stroke="{color}" stroke-width="1.5"/>'
                )
            elements.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}"/>')
            elements.append(
                _svg_text(
                    x,
                    bottom + 20,
                    f"{level:g}",
                    text_anchor="middle",
                    font_size="11",
                    fill="#486581",
                )
            )
            elements.append(
                _svg_text(
                    x,
                    bottom + 37,
                    variant_id,
                    text_anchor="middle",
                    font_size="10",
                    fill="#829ab1",
                )
            )
        elements.append(_polyline(points, color, 2.6))
        elements.append(
            _svg_text(
                left,
                top - 18,
                title,
                font_size="15",
                font_weight="650",
                fill="#243b53",
            )
        )
        elements.append(
            _svg_text(
                left,
                top + 2,
                y_label,
                font_size="11",
                fill="#627d98",
            )
        )
        elements.append(
            _svg_text(
                left + panel_w / 2,
                bottom + 58,
                x_label,
                text_anchor="middle",
                font_size="12",
                fill="#486581",
            )
        )
    elements.append("</svg>")
    return "\n".join(elements) + "\n"


def render_tradeoff(rows: list[dict[str, Any]]) -> str:
    width, height = 960, 650
    elements = _svg_header(
        width,
        height,
        "Control effort versus pole-angle error",
        "One point per trained policy (n=27); log axes retain stable and failed runs",
    )
    left, top, plot_w, plot_h = 105.0, 115.0, 775.0, 430.0
    bottom = top + plot_h
    x_values = [float(row["mean_abs_requested_effort"]) for row in rows]
    y_values = [float(row["mean_pole_angle_rms_radians"]) for row in rows]
    x_min, x_max = min(x_values) * 0.75, max(x_values) * 1.25
    y_min, y_max = min(y_values) * 0.75, max(y_values) * 1.25
    log_x_min, log_x_max = math.log10(x_min), math.log10(x_max)
    log_y_min, log_y_max = math.log10(y_min), math.log10(y_max)

    def x_scale(value: float) -> float:
        return left + plot_w * (math.log10(value) - log_x_min) / (log_x_max - log_x_min)

    def y_scale(value: float) -> float:
        return bottom - plot_h * (math.log10(value) - log_y_min) / (log_y_max - log_y_min)

    for x_value in (0.1, 1.0, 10.0, 100.0):
        if not x_min <= x_value <= x_max:
            continue
        x = x_scale(x_value)
        elements.append(_svg_line(x, top, x, bottom, stroke="#e5e7eb", stroke_width="1"))
        elements.append(
            _svg_text(
                x,
                bottom + 24,
                f"{x_value:.1f}",
                text_anchor="middle",
                font_size="11",
                fill="#627d98",
            )
        )
    for y_degrees in (1.0, 3.0, 10.0, 30.0):
        y_value = math.radians(y_degrees)
        if not y_min <= y_value <= y_max:
            continue
        y = y_scale(y_value)
        elements.append(_svg_line(left, y, left + plot_w, y, stroke="#e5e7eb", stroke_width="1"))
        elements.append(
            _svg_text(
                left - 10,
                y + 4,
                f"{y_degrees:g}°",
                text_anchor="end",
                font_size="11",
                fill="#627d98",
            )
        )
    for row in rows:
        x = x_scale(float(row["mean_abs_requested_effort"]))
        y = y_scale(float(row["mean_pole_angle_rms_radians"]))
        color = FACTOR_COLORS[str(row["factor"])]
        elements.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}" '
            'fill-opacity="0.78" stroke="#ffffff" stroke-width="1"/>'
        )
    elements.append(
        _svg_text(
            left + plot_w / 2,
            605,
            "Mean absolute requested effort",
            text_anchor="middle",
            font_size="14",
            font_weight="600",
            fill="#243b53",
        )
    )
    elements.append(
        _svg_text(
            25,
            top + plot_h / 2,
            "Pole-angle RMS",
            text_anchor="middle",
            font_size="14",
            font_weight="600",
            fill="#243b53",
            transform=f"rotate(-90 25 {top + plot_h / 2:.1f})",
        )
    )
    legend_x = 112.0
    for factor in ["baseline", "observation", "reward", "action", "termination"]:
        elements.append(
            f'<circle cx="{legend_x:.1f}" cy="92" r="5" fill="{FACTOR_COLORS[factor]}"/>'
        )
        elements.append(_svg_text(legend_x + 10, 96, factor, font_size="11", fill="#486581"))
        legend_x += 115
    elements.append("</svg>")
    return "\n".join(elements) + "\n"


def write_outputs(source: Path, output: Path, study: dict[str, Any], rows: dict[str, Any]) -> None:
    manifests_output = output / "manifests"
    manifests_output.mkdir(parents=True, exist_ok=True)
    for path in sorted((source / "manifests").glob("*.json")):
        shutil.copyfile(path, manifests_output / path.name)

    for stage in ("screening", "final"):
        stage_output = output / "evaluations" / stage
        stage_output.mkdir(parents=True, exist_ok=True)
        for path in sorted((source / "evaluations" / stage).glob("*.json")):
            shutil.copyfile(path, stage_output / path.name)
    shutil.copyfile(source / "study_summary.json", output / "study_summary.json")

    data_dir = output / "data"
    _write_csv(
        data_dir / "run_registry.csv",
        rows["run_registry"],
        list(rows["run_registry"][0]),
    )
    _write_csv(
        data_dir / "training_curves.csv",
        rows["training_curves"],
        list(rows["training_curves"][0]),
    )
    _write_csv(
        data_dir / "run_metrics.csv",
        rows["run_metrics"],
        list(rows["run_metrics"][0]),
    )
    _write_csv(
        data_dir / "episode_metrics.csv",
        rows["episode_metrics"],
        list(rows["episode_metrics"][0]),
    )
    _write_csv(
        data_dir / "paired_effects.csv",
        rows["paired_effects"],
        list(rows["paired_effects"][0]),
    )
    _write_csv(
        data_dir / "condition_summary.csv",
        rows["condition_summary"],
        list(rows["condition_summary"][0]),
    )
    _write_csv(
        data_dir / "failure_composition.csv",
        rows["failure_composition"],
        list(rows["failure_composition"][0]),
    )

    plots = output / "plots"
    plots.mkdir(parents=True, exist_ok=True)
    (plots / "learning_dynamics.svg").write_text(render_learning_dynamics(rows["training_curves"]))
    (plots / "final_performance.svg").write_text(render_final_performance(rows["run_metrics"]))
    (plots / "factor_sensitivity.svg").write_text(render_sensitivity(rows["run_metrics"]))
    (plots / "control_sensitivity.svg").write_text(render_control_sensitivity(rows["run_metrics"]))
    (plots / "effort_error_tradeoff.svg").write_text(render_tradeoff(rows["run_metrics"]))

    receipt = {
        "schema_version": 1,
        "source_study_summary": study["study_summary"],
        "row_counts": {key: len(value) for key, value in rows.items()},
        "plots": sorted(path.name for path in plots.glob("*.svg")),
    }
    (output / "build_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/phase2"))
    args = parser.parse_args()
    study = load_study(args.source)
    rows = derive_rows(study)
    write_outputs(args.source, args.output, study, rows)
    print(json.dumps({key: len(value) for key, value in rows.items()}, indent=2))


if __name__ == "__main__":
    main()
