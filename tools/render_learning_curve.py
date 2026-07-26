#!/usr/bin/env python3
"""Render a dependency-free SVG from a checkpoint learning-curve artifact."""

from __future__ import annotations

import argparse
import html
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _line(x1: float, y1: float, x2: float, y2: float, **attrs: Any) -> str:
    attributes = " ".join(f'{key.replace("_", "-")}="{value}"' for key, value in attrs.items())
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" {attributes}/>'


def _text(x: float, y: float, value: str, **attrs: Any) -> str:
    attributes = " ".join(f'{key.replace("_", "-")}="{value}"' for key, value in attrs.items())
    return f'<text x="{x:.1f}" y="{y:.1f}" {attributes}>{html.escape(value)}</text>'


def _polyline(points: list[tuple[float, float]], color: str) -> str:
    encoded = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return (
        f'<polyline points="{encoded}" fill="none" stroke="{color}" '
        'stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>'
    )


def _panel(
    *,
    evaluations: list[dict[str, Any]],
    x_scale: Callable[[float], float],
    top: float,
    height: float,
    left: float,
    width: float,
    value_key: str,
    y_max: float,
    label: str,
    color: str,
    tick_formatter: Callable[[float], str],
) -> list[str]:
    elements: list[str] = []
    bottom = top + height
    for tick in range(5):
        value = y_max * tick / 4
        y = bottom - height * tick / 4
        elements.append(_line(left, y, left + width, y, stroke="#d9e2ec", stroke_width="1"))
        elements.append(
            _text(
                left - 12,
                y + 5,
                tick_formatter(value),
                text_anchor="end",
                font_size="13",
                fill="#486581",
            )
        )

    points = [
        (
            x_scale(float(evaluation["training_transitions"])),
            bottom - height * float(evaluation[value_key]) / y_max,
        )
        for evaluation in evaluations
    ]
    elements.append(_polyline(points, color))
    for x, y in points:
        elements.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}"/>')

    elements.append(
        _text(
            left - 65,
            top + height / 2,
            label,
            text_anchor="middle",
            font_size="14",
            font_weight="600",
            fill="#243b53",
            transform=f"rotate(-90 {left - 65:.1f} {top + height / 2:.1f})",
        )
    )
    return elements


def render_svg(payload: dict[str, Any]) -> str:
    evaluations = payload.get("evaluations", [])
    if not evaluations:
        raise ValueError("learning-curve artifact contains no evaluations")
    if any(evaluation.get("training_transitions") is None for evaluation in evaluations):
        raise ValueError("every evaluation must include training_transitions")

    evaluations = sorted(evaluations, key=lambda item: int(item["training_transitions"]))
    width = 960
    left, right = 120.0, 55.0
    plot_width = width - left - right
    x_max = max(float(item["training_transitions"]) for item in evaluations)
    if x_max <= 0:
        raise ValueError("training_transitions must be positive")

    def x_scale(transitions: float) -> float:
        return left + plot_width * transitions / x_max

    episode_limit = float(payload.get("episode_limit_seconds", 5.0))
    top_panel_top, top_panel_height = 105.0, 220.0
    bottom_panel_top, bottom_panel_height = 405.0, 180.0
    elements = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="700" viewBox="0 0 960 700">',
        '<rect width="960" height="700" fill="#f8fafc"/>',
        _text(
            width / 2,
            42,
            "CartPole checkpoint learning curve",
            text_anchor="middle",
            font_size="24",
            font_weight="700",
            fill="#102a43",
        ),
        _text(
            width / 2,
            68,
            "Fixed seeds; each point independently evaluates one saved policy",
            text_anchor="middle",
            font_size="14",
            fill="#486581",
        ),
    ]

    elements.extend(
        _panel(
            evaluations=evaluations,
            x_scale=x_scale,
            top=top_panel_top,
            height=top_panel_height,
            left=left,
            width=plot_width,
            value_key="mean_balance_seconds",
            y_max=episode_limit,
            label="Mean balance time (s)",
            color="#1565c0",
            tick_formatter=lambda value: f"{value:.1f}",
        )
    )
    elements.extend(
        _panel(
            evaluations=evaluations,
            x_scale=x_scale,
            top=bottom_panel_top,
            height=bottom_panel_height,
            left=left,
            width=plot_width,
            value_key="time_limit_fraction",
            y_max=1.0,
            label="Reached time limit",
            color="#00897b",
            tick_formatter=lambda value: f"{value:.0%}",
        )
    )

    random_baseline = payload.get("random_baseline")
    if random_baseline is not None:
        random_seconds = float(random_baseline["mean_balance_seconds"])
        baseline_y = top_panel_top + top_panel_height * (1 - random_seconds / episode_limit)
        elements.append(
            _line(
                left,
                baseline_y,
                left + plot_width,
                baseline_y,
                stroke="#d97706",
                stroke_width="2",
                stroke_dasharray="7 6",
            )
        )
        elements.append(
            _text(
                left + plot_width - 4,
                baseline_y - 7,
                f"random baseline {random_seconds:.2f}s",
                text_anchor="end",
                font_size="13",
                fill="#b45309",
            )
        )

    x_axis_y = bottom_panel_top + bottom_panel_height
    for tick in range(5):
        transitions = x_max * tick / 4
        x = x_scale(transitions)
        elements.append(_line(x, x_axis_y, x, x_axis_y + 7, stroke="#486581", stroke_width="1"))
        elements.append(
            _text(
                x,
                x_axis_y + 27,
                f"{transitions / 1_000_000:.1f}",
                text_anchor="middle",
                font_size="13",
                fill="#486581",
            )
        )
    elements.append(
        _text(
            left + plot_width / 2,
            655,
            "Training transitions (millions)",
            text_anchor="middle",
            font_size="15",
            font_weight="600",
            fill="#243b53",
        )
    )
    elements.append("</svg>")
    return "\n".join(elements) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text())
    svg = render_svg(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg)
    print(args.output)


if __name__ == "__main__":
    main()
