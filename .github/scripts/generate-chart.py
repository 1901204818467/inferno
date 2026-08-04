"""Generate chart.svg from prices.jsonl for the README.

Reads the daily price snapshot history and renders a clean SVG sparkline
of net profit over time (instabuy side). Handles 0, 1, and 2+ data points.
Zero external dependencies — just writes raw SVG text.
"""

import json
import os
import sys

W = 700
H = 180
PAD_L = 56
PAD_R = 12
PAD_T = 28
PAD_B = 28
COLOR_LINE = "#FF6B35"
COLOR_FILL = "#FF6B3522"
COLOR_TEXT = "#57606a"
COLOR_GRID = "#d0d7de33"

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"


def fmt_axis(n):
    """Compact axis labels: 10.1M, 500K, etc."""
    if n >= 1000000:
        s = "%.1f" % (n / 1000000.0)
        return s.rstrip("0").rstrip(".") + "M"
    if n >= 1000:
        s = "%.0f" % (n / 1000.0)
        return s + "K"
    return str(int(n))


def main():
    pts = []
    try:
        with open("prices.jsonl", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                net = d.get("net_ib")
                date = d.get("date")
                if net is not None and date:
                    pts.append((date, int(net)))
    except FileNotFoundError:
        pass

    if len(pts) < 2:
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"'
            ' viewBox="0 0 %d %d">\n' % (W, H, W, H)
            + '<rect width="%d" height="%d" fill="transparent"/>\n' % (W, H)
            + '<text x="%d" y="%d" text-anchor="middle"'
            ' font-family="%s" font-size="13" fill="%s">'
            "not enough data yet — chart will appear after 2+ days</text>\n"
            % (W // 2, H // 2, FONT, COLOR_TEXT)
            + "</svg>\n"
        )
        with open("chart.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        print("chart: not enough data (%d point(s)), wrote placeholder" % len(pts))
        return

    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B

    values = [v for _, v in pts]
    vmin = min(values)
    vmax = max(values)
    if vmin == vmax:
        vmin -= 1
        vmax += 1
    pad = (vmax - vmin) * 0.1 or 100000
    vmin -= pad
    vmax += pad

    def y(val):
        frac = (val - vmin) / (vmax - vmin) if vmax > vmin else 0.5
        return PAD_T + plot_h * (1.0 - frac)

    def x(i):
        if len(pts) == 1:
            return PAD_L + plot_w / 2.0
        return PAD_L + plot_w * i / (len(pts) - 1)

    coords = " ".join("%.1f,%.1f" % (x(i), y(v)) for i, (_, v) in enumerate(pts))

    area_coords = (
        "%.1f,%.1f " % (x(0), PAD_T + plot_h)
        + coords
        + " %.1f,%.1f" % (x(len(pts) - 1), PAD_T + plot_h)
    )

    y_ticks = []
    for frac in (0.0, 0.5, 1.0):
        val = vmin + (vmax - vmin) * frac
        y_ticks.append((y(val), fmt_axis(val)))

    max_labels = 8
    step = max(1, (len(pts) - 1) // (max_labels - 1)) if len(pts) > 1 else 1
    x_labels = []
    if len(pts) <= 1:
        x_labels.append((x(0), pts[0][0]))
    else:
        indices = list(range(0, len(pts), step))
        if indices[-1] != len(pts) - 1:
            indices.append(len(pts) - 1)
        for i in indices:
            x_labels.append((x(i), pts[i][0]))

    svg_parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"'
        ' viewBox="0 0 %d %d">' % (W, H, W, H),
        '<rect width="%d" height="%d" fill="transparent"/>' % (W, H),
        '<text x="%d" y="18" text-anchor="middle"'
        ' font-family="%s" font-size="13" font-weight="600" fill="%s">'
        "Daily Net Profit (instabuy)</text>" % (W // 2, FONT, "#24292f"),
        *[
            '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f"'
            ' stroke="%s" stroke-width="1"/>'
            % (PAD_L, yv, W - PAD_R, yv, COLOR_GRID)
            for yv, _ in y_ticks
        ],
        '<polygon points="%s" fill="%s" stroke="none"/>' % (area_coords, COLOR_FILL),
        '<polyline points="%s" fill="none" stroke="%s"'
        ' stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
        % (coords, COLOR_LINE),
        *[
            '<text x="%d" y="%.1f" text-anchor="end"'
            ' font-family="%s" font-size="11" fill="%s"'
            ' dominant-baseline="middle">%s</text>'
            % (PAD_L - 4, yv, FONT, COLOR_TEXT, label)
            for yv, label in y_ticks
        ],
        *[
            '<text x="%.1f" y="%d" text-anchor="middle"'
            ' font-family="%s" font-size="10" fill="%s">%s</text>'
            % (xv, H - 8, FONT, COLOR_TEXT, label)
            for xv, label in x_labels
        ],
        '<text x="%d" y="%.1f" text-anchor="start"'
        ' font-family="%s" font-size="11" font-weight="600" fill="%s"'
        ' dominant-baseline="middle">%s</text>'
        % (
            x(len(pts) - 1) + 6,
            y(values[-1]),
            FONT,
            COLOR_LINE,
            fmt_axis(values[-1]) + "/day",
        ),
        "</svg>",
    ]

    with open("chart.svg", "w", encoding="utf-8") as f:
        f.write("\n".join(svg_parts))
    print("chart: %d data points, net range %s .. %s -> chart.svg"
          % (len(pts), fmt_axis(vmin + pad), fmt_axis(vmax - pad)))


if __name__ == "__main__":
    main()

