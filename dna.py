"""Rotating ASCII-art DNA double helix animation for the terminal (standard library only)."""

import argparse
import math
import os
import random
import sys
import time
from shutil import get_terminal_size

COMPLEMENT = {"A": "T", "T": "A", "G": "C", "C": "G"}
BACKBONE_RAMP = ".:-=+*oO#%@"
RUNG_RAMP = ".-=+"
RUNG_SPACING = 3

STRAND_A_COLORS = (17, 18, 19, 20, 26, 32, 39, 45, 51, 87, 159, 195)
STRAND_B_COLORS = (52, 88, 124, 160, 166, 202, 208, 214, 220, 226, 227, 229)
RUNG_COLORS = (236, 238, 240, 242, 245, 249, 252)
BASE_COLORS = {"A": "38;5;46", "T": "38;5;203", "G": "38;5;226", "C": "38;5;87"}
TITLE_COLORS = (51, 45, 39, 75, 111, 147, 183, 219, 213, 207)

TITLE = "D N A   D O U B L E   H E L I X"
FOOTER = "press Ctrl-C to stop"

HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
HOME = "\033[H"
CLEAR_SCREEN = "\033[2J"
CLEAR_BELOW = "\033[J"
CLEAR_EOL = "\033[K"
RESET = "\033[0m"


def build_sequence(length):
    rng = random.Random(20240517)
    return "".join(rng.choice("ATGC") for _ in range(length))


SEQUENCE = build_sequence(1024)


def clamp01(value):
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def ramp_pick(ramp, position):
    return ramp[int(round(clamp01(position) * (len(ramp) - 1)))]


def strand_color(palette, depth, use_color):
    if not use_color:
        return None
    return "38;5;%d" % palette[int(round(clamp01(depth) * (len(palette) - 1)))]


def rung_color(depth, use_color):
    if not use_color:
        return None
    return "38;5;%d" % RUNG_COLORS[int(round(clamp01(depth) * (len(RUNG_COLORS) - 1)))]


def base_color(base, depth, use_color):
    if not use_color:
        return None
    weight = "1" if depth >= 0.5 else "2"
    return weight + ";" + BASE_COLORS[base]


def stamp_text(chars, colors, row, cols, text, use_color, gradient, dim_color):
    if not 0 <= row < len(chars):
        return
    text = text[:cols]
    start = max(0, (cols - len(text)) // 2)
    span = max(1, len(text) - 1)
    for offset, glyph in enumerate(text):
        col = start + offset
        if 0 <= col < cols:
            chars[row][col] = glyph
            if use_color:
                if gradient:
                    tint = TITLE_COLORS[int(round(offset / span * (len(TITLE_COLORS) - 1)))]
                    colors[row][col] = "1;38;5;%d" % tint
                else:
                    colors[row][col] = dim_color


def build_frame(cols, rows, angle, pitch, use_color, fps):
    chars = [[" "] * cols for _ in range(rows)]
    colors = [[None] * cols for _ in range(rows)]
    depths = [[-1.0] * cols for _ in range(rows)]

    show_chrome = rows >= 8 and cols >= 24
    top = 1 if show_chrome else 0
    helix_rows = rows - 2 if show_chrome else rows

    center = cols // 2
    fill = cols // 2 - 2
    cap = max(18, helix_rows)
    amplitude = max(0, min(fill, cap))
    twist = 2.0 * math.pi / max(2.0, pitch)

    def plot(row, col, depth, glyph, color):
        if glyph != " " and 0 <= row < rows and 0 <= col < cols and depth > depths[row][col]:
            depths[row][col] = depth
            chars[row][col] = glyph
            colors[row][col] = color

    for local_row in range(helix_rows):
        row = top + local_row
        theta0 = local_row * twist + angle
        theta1 = theta0 + math.pi
        depth0 = (math.sin(theta0) + 1.0) * 0.5
        depth1 = (math.sin(theta1) + 1.0) * 0.5
        col0 = int(round(center + amplitude * math.cos(theta0)))
        col1 = int(round(center + amplitude * math.cos(theta1)))

        if local_row % RUNG_SPACING == 0 and amplitude >= 1:
            base = SEQUENCE[local_row % len(SEQUENCE)]
            mate = COMPLEMENT[base]
            if col0 != col1:
                lo, hi = (col0, col1) if col0 < col1 else (col1, col0)
                depth_lo, depth_hi = (depth0, depth1) if col0 < col1 else (depth1, depth0)
                width = hi - lo
                for col in range(lo + 1, hi):
                    frac = (col - lo) / width
                    depth_c = depth_lo + frac * (depth_hi - depth_lo)
                    plot(row, col, depth_c, ramp_pick(RUNG_RAMP, depth_c),
                         rung_color(depth_c, use_color))
            glyph0 = base if depth0 >= 0.5 else base.lower()
            glyph1 = mate if depth1 >= 0.5 else mate.lower()
            plot(row, col0, depth0, glyph0, base_color(base, depth0, use_color))
            plot(row, col1, depth1, glyph1, base_color(mate, depth1, use_color))
        else:
            plot(row, col0, depth0, ramp_pick(BACKBONE_RAMP, depth0),
                 strand_color(STRAND_A_COLORS, depth0, use_color))
            plot(row, col1, depth1, ramp_pick(BACKBONE_RAMP, depth1),
                 strand_color(STRAND_B_COLORS, depth1, use_color))

    if show_chrome:
        stamp_text(chars, colors, 0, cols, TITLE, use_color, True, None)
        footer = "%s   -   %d fps" % (FOOTER, int(round(fps)))
        stamp_text(chars, colors, rows - 1, cols, footer, use_color, False, "38;5;240")

    return render(chars, colors, cols, rows, use_color)


def render(chars, colors, cols, rows, use_color):
    lines = []
    for row in range(rows):
        row_chars = chars[row]
        if not use_color:
            lines.append("".join(row_chars) + CLEAR_EOL)
            continue
        row_colors = colors[row]
        parts = []
        active = None
        for col in range(cols):
            glyph = row_chars[col]
            if glyph == " ":
                if active is not None:
                    parts.append(RESET)
                    active = None
                parts.append(" ")
                continue
            color = row_colors[col]
            if color != active:
                parts.append(RESET if color is None else "\033[" + color + "m")
                active = color
            parts.append(glyph)
        if active is not None:
            parts.append(RESET)
        parts.append(CLEAR_EOL)
        lines.append("".join(parts))
    return "\n".join(lines)


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Rotating 3D ASCII DNA double helix.")
    parser.add_argument("--fps", type=float, default=20.0, help="frames per second (1-60)")
    parser.add_argument("--period", type=float, default=6.0, help="seconds per full rotation")
    parser.add_argument("--pitch", type=float, default=12.0, help="rows per helical turn")
    parser.add_argument("--width", type=int, default=None, help="force column count")
    parser.add_argument("--no-color", action="store_true", help="render in monochrome")
    return parser.parse_args(argv)


def silence_stdout():
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        os.close(devnull)
    except (OSError, ValueError):
        pass


def animate(args):
    use_color = not args.no_color and os.environ.get("NO_COLOR") is None
    fps = args.fps if args.fps and args.fps > 0 else 20.0
    fps = max(1.0, min(fps, 60.0))
    frame_time = 1.0 / fps
    period = args.period if args.period and args.period > 0 else 6.0
    angular_speed = 2.0 * math.pi / period
    pitch = args.pitch if args.pitch and args.pitch >= 2.0 else 12.0

    out = sys.stdout
    last_size = None
    out.write(HIDE_CURSOR + CLEAR_SCREEN)
    out.flush()
    start = time.monotonic()
    try:
        while True:
            frame_start = time.monotonic()
            size = get_terminal_size((80, 24))
            cols = max(1, args.width if args.width else size.columns)
            rows = max(1, size.lines)
            if (cols, rows) != last_size:
                out.write(CLEAR_SCREEN)
                last_size = (cols, rows)
            angle = (frame_start - start) * angular_speed
            out.write(HOME + build_frame(cols, rows, angle, pitch, use_color, fps) + CLEAR_BELOW)
            out.flush()
            remaining = frame_time - (time.monotonic() - frame_start)
            if remaining > 0:
                time.sleep(remaining)
    except KeyboardInterrupt:
        pass
    except BrokenPipeError:
        silence_stdout()
    finally:
        try:
            out.write(RESET + SHOW_CURSOR + CLEAR_BELOW + "\n")
            out.flush()
        except (BrokenPipeError, ValueError, OSError):
            pass


def main(argv=None):
    animate(parse_args(argv))


if __name__ == "__main__":
    main()
