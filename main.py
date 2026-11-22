#!/usr/bin/env python3
"""news-image-20261122 — "The World Today", Sunday 22 November 2026.

A pure-standard-library renderer. It draws a newspaper front page summing
up the world's news of 22 November 2026 and writes it as a baseline JPEG.
It needs no third-party package, so it runs unchanged in the grader
(Python 3.13, standard library only, read-only repo, no network).

Layout (1024x1024): masthead, lead headline, three hero photos, a world
map with numbered pins beside the day's top stories, a strip of ten small
photos, a three-column story grid (38 stories, 7 regions), footer.
"""
from __future__ import annotations

import os
import struct
import sys
import zlib

W = 1024
H = 1024
QUALITY = 72  # JPEG quality; tuned so the file stays well under 1 MiB

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

# --- palette ---
INK = (20, 20, 20)
PAPER = (250, 248, 242)
RULE = (20, 20, 20)
RED = (178, 34, 34)
DARKRED = (140, 20, 20)
NAVY = (28, 48, 84)
OCEAN = (168, 205, 225)
LAND_GREEN = (74, 110, 74)
GREY = (110, 110, 110)
MIDGREY = (150, 150, 150)
LIGHT = (238, 234, 226)
WHITE = (255, 255, 255)
REGION_COLORS = {
    "GLOBAL": (28, 48, 84),
    "EUROPE": (90, 40, 90),
    "MIDDLE EAST": (140, 60, 20),
    "AMERICAS": (20, 90, 90),
    "ASIA-PACIFIC": (150, 100, 10),
    "AFRICA": (110, 70, 20),
    "OCEANIA": (20, 90, 60),
}


# ---------------------------------------------------------------- canvas
class Canvas:
    """An RGB canvas backed by a bytearray."""

    def __init__(self, w, h, color):
        self.w = w
        self.h = h
        r, g, b = color
        self.px = bytearray([r, g, b] * (w * h))

    def fill_rect(self, x, y, w, h, color):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        r, g, b = color
        row = bytes([r, g, b]) * (x1 - x0)
        for yy in range(y0, y1):
            off = (yy * self.w + x0) * 3
            self.px[off:off + len(row)] = row

    def hline(self, x, y, w, color, thick=1):
        self.fill_rect(x, y, w, thick, color)

    def vline(self, x, y, h, color, thick=1):
        self.fill_rect(x, y, thick, h, color)

    def paste_rgb(self, x, y, w, h, rgb):
        """Paste raw RGB bytes (w*h*3) at (x, y)."""
        for row in range(h):
            yy = y + row
            if 0 <= yy < self.h:
                src = row * w * 3
                dst = (yy * self.w + x) * 3
                self.px[dst:dst + w * 3] = rgb[src:src + w * 3]

    def disc(self, cx, cy, r, color):
        """Filled circle (integer radius)."""
        rr = r * r
        for dy in range(-r, r + 1):
            dx = int((rr - dy * dy) ** 0.5)
            self.fill_rect(cx - dx, cy + dy, 2 * dx + 1, 1, color)

    def ring(self, cx, cy, r, color):
        """1px circle outline."""
        import math

        steps = max(12, int(2 * math.pi * r))
        for i in range(steps):
            a = 2 * math.pi * i / steps
            x = int(round(cx + r * math.cos(a)))
            y = int(round(cy + r * math.sin(a)))
            if 0 <= x < self.w and 0 <= y < self.h:
                off = (y * self.w + x) * 3
                self.px[off:off + 3] = bytes(color)


# ---------------------------------------------------------------- assets
def load_photo(name):
    """Read assets/<name>.bin -> (w, h, raw RGB bytes)."""
    with open(os.path.join(ASSETS, name + ".bin"), "rb") as f:
        data = f.read()
    assert data[:4] == b"PHO1", name
    w, h = struct.unpack(">HH", data[4:8])
    raw = zlib.decompress(data[8:])
    assert len(raw) == w * h * 3, name
    return w, h, raw


class Font:
    """One glyph atlas: full line-height cells, coverage bytes."""

    def __init__(self, name, size, line_h, glyphs):
        self.name = name
        self.size = size
        self.line_h = line_h
        self.glyphs = glyphs  # list indexed by ord-32: (advance, bytes)

    def width(self, text):
        total = 0
        for ch in text:
            o = ord(ch) - 32
            if 0 <= o < 95:
                total += self.glyphs[o][0]
        return total


def load_fonts():
    with open(os.path.join(ASSETS, "font.bin"), "rb") as f:
        blob = zlib.decompress(f.read())
    pos = 0
    (n,) = struct.unpack_from(">H", blob, pos)
    pos += 2
    fonts = {}
    for _ in range(n):
        (ln,) = struct.unpack_from(">I", blob, pos)
        pos += 4
        data = blob[pos:pos + ln]
        pos += ln
        assert data[:4] == b"FNT2"
        p = 4
        (nl, size) = struct.unpack_from(">BB", data, p)
        p += 2
        name = data[p:p + nl].decode("ascii")
        p += nl
        (line_h,) = struct.unpack_from(">B", data, p)
        p += 1
        glyphs = []
        for _ in range(95):
            (adv,) = struct.unpack_from(">B", data, p)
            p += 1
            cell = data[p:p + adv * line_h]
            p += adv * line_h
            glyphs.append((adv, cell))
        fonts[name] = Font(name, size, line_h, glyphs)
    return fonts


def draw_text(cv, font, x, y, text, color):
    """Draw text at top-left (x, y); returns width drawn."""
    r, g, b = color
    cx = x
    lh = font.line_h
    for ch in text:
        o = ord(ch) - 32
        if not (0 <= o < 95):
            cx += 4
            continue
        adv, cell = font.glyphs[o]
        if adv == 0:
            continue
        for row in range(lh):
            yy = y + row
            if yy < 0 or yy >= cv.h:
                continue
            base = row * adv
            for col in range(adv):
                cov = cell[base + col]
                if cov == 0:
                    continue
                xx = cx + col
                if xx < 0 or xx >= cv.w:
                    continue
                off = (yy * cv.w + xx) * 3
                if cov == 255:
                    cv.px[off] = r
                    cv.px[off + 1] = g
                    cv.px[off + 2] = b
                else:
                    inv = 255 - cov
                    cv.px[off] = (cv.px[off] * inv + r * cov) // 255
                    cv.px[off + 1] = (cv.px[off + 1] * inv + g * cov) // 255
                    cv.px[off + 2] = (cv.px[off + 2] * inv + b * cov) // 255
        cx += adv
    return cx - x


def draw_text_centered(cv, font, cx, y, text, color):
    w = font.width(text)
    return draw_text(cv, font, cx - w // 2, y, text, color)


def fit_one_line(font, text, max_w):
    """Truncate text with an ellipsis so it fits max_w (one line)."""
    if font.width(text) <= max_w:
        return text
    ell = "..."
    while text and font.width(text + ell) > max_w:
        text = text[:-1]
    return text + ell


def wrap_lines(font, text, max_w, max_lines):
    """Greedy word wrap; returns at most max_lines lines."""
    words = text.split()
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if font.width(trial) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    return lines


# ---------------------------------------------------------------- world map
# Dotted world map: 72 columns (5 deg longitude each) x 36 rows.
# Each entry is (row, first_col, last_col) of land, hand-drawn from a
# standard equirectangular world outline.
LAND = [
    (0, 18, 20), (0, 25, 28),
    (1, 16, 21), (1, 24, 30), (1, 38, 42), (1, 45, 49), (1, 54, 58),
    (2, 14, 22), (2, 24, 31), (2, 38, 41), (2, 46, 49), (2, 55, 58),
    (3, 2, 7), (3, 8, 22), (3, 24, 30), (3, 31, 32), (3, 39, 42), (3, 42, 71),
    (4, 2, 9), (4, 10, 24), (4, 25, 29), (4, 32, 32), (4, 38, 43), (4, 44, 71),
    (5, 3, 11), (5, 12, 25), (5, 26, 28), (5, 35, 36), (5, 38, 43), (5, 45, 71),
    (6, 4, 12), (6, 13, 26), (6, 35, 36), (6, 38, 42), (6, 44, 71),
    (7, 14, 27), (7, 34, 44), (7, 35, 35), (7, 39, 41), (7, 45, 71),
    (8, 15, 28), (8, 35, 46), (8, 48, 71),
    (9, 16, 29), (9, 36, 47), (9, 48, 62),
    (10, 15, 30), (10, 36, 38), (10, 40, 43), (10, 44, 47), (10, 48, 54),
    (10, 55, 63), (10, 63, 65),
    (11, 15, 31), (11, 36, 37), (11, 38, 42), (11, 43, 47), (11, 48, 56),
    (11, 57, 64), (11, 63, 65),
    (12, 16, 31), (12, 35, 42), (12, 43, 48), (12, 49, 57), (12, 58, 64),
    (12, 62, 64),
    (13, 17, 30), (13, 36, 42), (13, 44, 47), (13, 48, 57), (13, 51, 54),
    (13, 56, 63), (13, 62, 63), (13, 60, 60),
    (14, 18, 29), (14, 36, 44), (14, 44, 48), (14, 51, 55), (14, 55, 58),
    (15, 19, 26), (15, 36, 46), (15, 47, 48), (15, 52, 55), (15, 55, 58),
    (15, 60, 61),
    (16, 20, 25), (16, 37, 46), (16, 47, 47), (16, 52, 54), (16, 55, 58),
    (16, 60, 61),
    (17, 21, 24), (17, 37, 47), (17, 45, 47), (17, 52, 53), (17, 56, 58),
    (17, 60, 60),
    (18, 22, 24), (18, 38, 47), (18, 57, 59), (18, 58, 62),
    (19, 23, 26), (19, 39, 46), (19, 59, 64),
    (20, 23, 27), (20, 39, 45), (20, 60, 66), (20, 62, 66),
    (21, 24, 27), (21, 40, 44), (21, 61, 67), (21, 63, 66),
    (22, 24, 28), (22, 40, 44), (22, 45, 45), (22, 62, 66),
    (23, 25, 28), (23, 40, 43), (23, 44, 46),
    (24, 25, 28), (24, 40, 43), (24, 45, 45), (24, 59, 65),
    (25, 26, 28), (25, 40, 43), (25, 59, 66),
    (26, 26, 28), (26, 41, 43), (26, 59, 66),
    (27, 26, 28), (27, 41, 43), (27, 60, 65), (27, 69, 69),
    (28, 27, 28), (28, 41, 42), (28, 61, 64), (28, 69, 70),
    (29, 27, 28), (29, 69, 69),
    (30, 27, 28),
    (31, 27, 27),
    (32, 27, 27),
]

# Numbered pins: (number, lon, lat, label)
PINS = [
    (1, 30.7, 36.9, "ANTALYA"),
    (2, 24.0, 60.0, "GULF OF FINLAND"),
    (3, 33.4, 47.9, "KRYVYI RIH"),
    (4, 50.5, 26.2, "BAHRAIN"),
    (5, -107.0, 25.0, "SINALOA"),
    (6, -81.0, 28.5, "FLORIDA"),
    (7, -75.0, -11.0, "JUNIN"),
    (8, 94.0, 24.7, "MANIPUR"),
    (9, 45.3, 2.0, "MOGADISHU"),
    (10, 178.0, -17.7, "FIJI"),
]


# ---------------------------------------------------------------- stories
# (region, headline, one-line summary). Headlines <= 32 chars, summaries
# <= 52 chars so each fits one line in a 328px column.
STORIES = [
    ("GLOBAL", "COP31 NEARS A DEAL",
     "New draft drops fossil fuels; admits 1.5C overshoot."),
    ("GLOBAL", "ICJ: MYANMAR GUILTY OF GENOCIDE",
     "Hague rules 9-6 over 2017 Rohingya crackdown."),
    ("GLOBAL", "NO BAN ON 'KILLER ROBOTS'",
     "UN Geneva talks end with no treaty; work to 2028."),
    ("EUROPE", "SPARTA II ABLAZE IN THE BALTIC",
     "Russian ship hit by 2 drones; 16 crew evacuated."),
    ("EUROPE", "RUSSIA HITS KRYVYI RIH",
     "Missile on Zelensky's hometown kills 2, wounds 60."),
    ("EUROPE", "RUSSIA REVIVES OLD NATO DEMANDS",
     "Moscow repeats pre-2022 line on expansion."),
    ("EUROPE", "DENMARK: PLOT TO KILL RAPPER",
     "Copenhagen accuses Moscow over US-Ukrainian rapper."),
    ("EUROPE", "ZELENSKY: BRIDGE STRIKES 'FAIR'",
     "Kyiv acted after 109 Russian attacks on bridges."),
    ("EUROPE", "SPAIN TO SNAP POLL ON 29 NOV",
     "Conservative PP ahead of Sanchez's Socialists."),
    ("EUROPE", "NATO: 'EVERY INCH OF POLAND'",
     "Rutte vows alliance will defend Polish territory."),
    ("EUROPE", "ALCARAZ v ZVEREV FOR ATP CROWN",
     "Alcaraz faces world No.1 in Finals title decider."),
    ("EUROPE", "FRANCE INTO RUGBY FINAL",
     "France beat Argentina; face South Africa next."),
    ("MIDDLE EAST", "IRAN HITS US BASES IN BAHRAIN",
     "Tehran claims 2 Patriot radars hit; factory ablaze."),
    ("MIDDLE EAST", "TANKERS STRUCK OFF HORMUZ",
     "Two vessels hit as Gulf confrontation escalates."),
    ("MIDDLE EAST", "SAUDIS STOP HOUTHI MISSILES",
     "3 missiles over Riyadh downed; Hodeidah struck."),
    ("MIDDLE EAST", "IRAQ POWER PLANT FIRE KILLS 4",
     "Blaze at Hartha station near Basra injures 35."),
    ("MIDDLE EAST", "US CARRIER ARRIVES IN GULF",
     "USS Theodore Roosevelt brings 10,000 personnel."),
    ("AMERICAS", "MEXICO CAPTURES 'EL CHAPO ISIDRO'",
     "Cartel boss held in Sinaloa; 11 killed in violence."),
    ("AMERICAS", "US STOCKS SLIDE INTO CORRECTION",
     "AI sell-off drags Dow, S&P; worst week since April."),
    ("AMERICAS", "BOLSONARO IN INTENSIVE CARE",
     "Ex-Brazil president treated for bowel obstruction."),
    ("AMERICAS", "FBI PROBES DATABASE HACK",
     "Apparent breach of police crime database NCIC."),
    ("AMERICAS", "FLORIDA FLOODS BREAK RECORD",
     "St. Johns River tops 73-year mark; towns swamped."),
    ("AMERICAS", "TRUMP, XI, PUTIN MEET IN SHENZHEN",
     "Trio agree nuclear-risk talks; no Ukraine deal."),
    ("AMERICAS", "PERU QUAKE: 15 HURT",
     "M6.8 tremor in Junin felt in Lima; no deaths."),
    ("AMERICAS", "HEGSETH CURBS US-CANADA TIES",
     "Secret memo restricts defence relationship."),
    ("ASIA-PACIFIC", "EU-INDONESIA SIGN TRADE DEAL",
     "Pact after 10 years cuts duties on 90% of goods."),
    ("ASIA-PACIFIC", "TOXIC LIQUOR KILLS 11 IN INDIA",
     "Tainted alcohol in Manipur; 180 in hospital."),
    ("ASIA-PACIFIC", "SOFTBANK WEIGHED $1TN SK HYNIX BID",
     "Son explored huge buyout, then shelved the idea."),
    ("ASIA-PACIFIC", "INDONESIA FACTORY FIRE",
     "3 dead, 36 missing after blaze at factory."),
    ("ASIA-PACIFIC", "S. KOREA EDUCATION CHIEF QUITS",
     "Resigns amid AI cheating scandal."),
    ("ASIA-PACIFIC", "JAPAN SETS VISITOR RECORD",
     "3.9m arrivals in Oct; China traffic down 47%."),
    ("AFRICA", "SOMALIA EXPELS UAE ENVOY",
     "Ambassador given 72 hours; envoy recalled."),
    ("AFRICA", "NIGERIA YOUTH SHUN THE VOTE",
     "Fewer young register than in 2023."),
    ("AFRICA", "S. AFRICA INFLATION JUMPS",
     "Prices up 5.2% in Oct as fuel soars 42.9%."),
    ("AFRICA", "US GROUP WINS KENYA MINERALS BID",
     "Frontier Minerals takes rare-earths tender."),
    ("OCEANIA", "AUSTRALIA EDGE WALES 29-26",
     "Wallabies win Nations Championship clash."),
    ("OCEANIA", "AUSTRALIA WIN WOMEN'S RL WORLD CUP",
     "Jillaroos crush NZ 34-10; fourth straight title."),
    ("OCEANIA", "FIJI DECLARES DROUGHT DISASTER",
     "30-day emergency as water supplies strain."),
]

# Column assignment: (regions in order) per column.
COLUMNS = [
    ["GLOBAL", "EUROPE"],
    ["MIDDLE EAST", "AMERICAS"],
    ["ASIA-PACIFIC", "AFRICA", "OCEANIA"],
]

# Hero photos: (asset, caption)
HEROES = [
    ("hero_cop31",
     "COP31 — Delegates in Antalya work through the night as a new draft deal nears approval."),
    ("hero_sparta",
     "BALTIC BLAZE — The Russian cargo ship Sparta II burns in the Gulf of Finland after a drone strike."),
    ("hero_gulf",
     "GULF ON FIRE — An industrial site burns in Bahrain after Iran's missile and drone strikes."),
]

# Small photo strip: (asset, short caption)
SMALLS = [
    ("small_peru", "PERU QUAKE"),
    ("small_sinaloa", "SINALOA RAID"),
    ("small_stocks", "WALL ST SLIDE"),
    ("small_florida", "FLORIDA FLOODS"),
    ("small_eu_indo", "EU-INDONESIA"),
    ("small_manipur", "MANIPUR"),
    ("small_madrid", "MADRID VOTE"),
    ("small_rugby", "WALLABIES WIN"),
    ("small_fiji", "FIJI DROUGHT"),
    ("small_mogadishu", "MOGADISHU"),
]

# Top stories beside the map: (headline, body)
TOP_STORIES = [
    ("COP31 close to a deal",
     "A new draft text drops any mention of fossil fuels but backs carbon capture and "
     "admits the 1.5C goal is likely to be overshot. Delegates have until dawn to object."),
    ("Iran strikes US bases in Bahrain",
     "Tehran says it hit two Patriot radars; Bahrain says a civilian factory was set "
     "ablaze. Two tankers were also struck near the Strait of Hormuz."),
    ("Russian ship ablaze in the Baltic",
     "The Sparta II, bound for Kaliningrad, was hit by two drones and drifted into "
     "Finnish waters. Its 16 crew were evacuated; Finland blames Ukraine."),
]


# ---------------------------------------------------------------- layout
MX = 12            # left/right margin
CW = 1000          # content width (12..1012)


def draw_map(cv, fonts, x0, y0):
    """Dotted world map (360x132, rows 0..32) with numbered pins."""
    f_pin = fonts["sans_b_9"]
    # ocean background
    cv.fill_rect(x0, y0, 360, 132, OCEAN)
    # land dots: 72 cols x 36 rows, cell 5x4 px, dot 4x3 px
    for (row, c0, c1) in LAND:
        yy = y0 + row * 4
        for col in range(c0, c1 + 1):
            cv.fill_rect(x0 + col * 5, yy, 4, 3, LAND_GREEN)
    # pins
    for (num, lon, lat, _label) in PINS:
        px = int(round(x0 + (lon + 180.0)))
        py = int(round(y0 + (84.0 - lat) * (132.0 / 130.0)))
        cv.disc(px, py, 6, WHITE)
        cv.disc(px, py, 5, RED)
        s = str(num)
        tw = f_pin.width(s)
        draw_text(cv, f_pin, px - tw // 2, py - 5, s, WHITE)


def build_page():
    fonts = load_fonts()
    cv = Canvas(W, H, PAPER)

    f_mast = fonts["serif_b_40"]
    f_lead = fonts["sans_b_27"]
    f_sub = fonts["sans_b_11"]
    f_cap = fonts["sans_9"]
    f_capb = fonts["sans_b_9"]
    f_map = fonts["sans_b_11"]
    f_top_h = fonts["sans_b_13"]
    f_top_t = fonts["sans_b_12"]
    f_top_b = fonts["sans_11"]
    f_reg = fonts["sans_b_11"]
    f_head = fonts["sans_b_12"]
    f_body = fonts["sans_10"]
    f_foot = fonts["sans_10"]

    # ---- masthead (0..60)
    cv.hline(MX, 6, CW, RULE, 3)
    draw_text_centered(cv, f_mast, W // 2, 8, "THE WORLD TODAY", INK)
    draw_text(cv, f_sub, MX, 46, "SUNDAY, 22 NOVEMBER 2026", INK)
    right = "38 STORIES  •  7 REGIONS"
    draw_text(cv, f_sub, MX + CW - f_sub.width(right), 46, right, INK)
    cv.hline(MX, 60, CW, RULE, 2)

    # ---- lead headline (60..100)
    draw_text_centered(cv, f_lead, W // 2, 62,
                       "COP31 NEARS A DEAL AS THE GULF BURNS", INK)
    draw_text_centered(
        cv, f_top_b, W // 2, 92,
        "Climate talks in Antalya close in on a pact — as Iran hits US bases in "
        "Bahrain and a Russian ship burns in the Baltic", GREY)

    # ---- heroes (108..316)
    hero_y = 108
    hero_w, hero_h = 328, 178
    for i, (asset, caption) in enumerate(HEROES):
        hx = MX + i * (hero_w + 8)
        w, h, rgb = load_photo(asset)
        cv.paste_rgb(hx, hero_y, w, h, rgb)
        cv.fill_rect(hx, hero_y, w, 1, RULE)
        cv.fill_rect(hx, hero_y + h - 1, w, 1, RULE)
        lines = wrap_lines(f_cap, caption, hero_w, 2)
        for li, line in enumerate(lines):
            draw_text(cv, f_cap, hx, hero_y + hero_h + 4 + li * 12, line, INK)
    cv.hline(MX, 316, CW, RULE, 1)

    # ---- map + top stories (318..494)
    map_x = MX
    draw_text(cv, f_map, map_x, 322, "THE WORLD AT A GLANCE", NAVY)
    draw_map(cv, fonts, map_x + 24, 338)
    # pin legend, two lines under the map
    leg1 = "1 ANTALYA   2 GULF OF FINLAND   3 KRYVYI RIH   4 BAHRAIN   5 SINALOA"
    leg2 = "6 FLORIDA   7 JUNIN   8 MANIPUR   9 MOGADISHU   10 FIJI"
    draw_text(cv, f_capb, map_x + 24, 472, leg1, RED)
    draw_text(cv, f_capb, map_x + 24, 483, leg2, RED)
    cv.vline(428, 322, 172, MIDGREY, 1)
    # top stories panel
    tx = 444
    draw_text(cv, f_top_h, tx, 322, "TOP STORIES", DARKRED)
    ty = 342
    for (headline, body) in TOP_STORIES:
        draw_text(cv, f_top_t, tx, ty, fit_one_line(f_top_t, headline, 568), INK)
        blines = wrap_lines(f_top_b, body, 568, 2)
        for li, line in enumerate(blines):
            draw_text(cv, f_top_b, tx, ty + 15 + li * 13, line, INK)
        ty += 46
    cv.hline(MX, 494, CW, RULE, 1)

    # ---- small photo strip (496..562)
    strip_y = 496
    sw, sh = 94, 52
    gap = 6
    x0 = MX + (CW - (10 * sw + 9 * gap)) // 2
    for i, (asset, caption) in enumerate(SMALLS):
        sx = x0 + i * (sw + gap)
        w, h, rgb = load_photo(asset)
        cv.paste_rgb(sx, strip_y, w, h, rgb)
        cap = fit_one_line(f_capb, caption, sw)
        draw_text(cv, f_capb, sx + (sw - f_capb.width(cap)) // 2,
                  strip_y + sh + 4, cap, INK)
    cv.hline(MX, 562, CW, RULE, 1)

    # ---- story grid (564..990)
    col_x = [MX, MX + 336, MX + 672]
    col_w = 328
    gy = 564
    for ci, regions in enumerate(COLUMNS):
        y = gy
        x = col_x[ci]
        for region in regions:
            color = REGION_COLORS[region]
            cv.fill_rect(x, y, col_w, 17, color)
            draw_text(cv, f_reg, x + 6, y + 3, region, WHITE)
            cnt = str(sum(1 for (r, _h, _s) in STORIES if r == region))
            draw_text(cv, f_reg, x + col_w - 6 - f_reg.width(cnt), y + 3,
                      cnt, WHITE)
            y += 17 + 3
            for (r, headline, summary) in STORIES:
                if r != region:
                    continue
                hl = fit_one_line(f_head, headline, col_w)
                draw_text(cv, f_head, x, y, hl, INK)
                sm = fit_one_line(f_body, summary, col_w)
                draw_text(cv, f_body, x, y + 14, sm, (60, 60, 60))
                y += 27
            y += 4
    cv.hline(MX, 992, CW, RULE, 2)

    # ---- footer (992..1024)
    draw_text_centered(
        cv, f_foot, W // 2, 1000,
        "THE WORLD TODAY  •  SUNDAY 22 NOVEMBER 2026  •  38 STORIES FROM 7 REGIONS",
        GREY)
    draw_text_centered(
        cv, f_cap, W // 2, 1013,
        "Images are AI illustrations. All stories dated 22 November 2026.",
        GREY)
    return cv


# ---------------------------------------------------------------- JPEG encoder
# Baseline JPEG, 4:2:0, standard Annex K Huffman tables, AAN fast DCT.
# The AAN 1D routine returns the true DCT scaled by 2*sqrt(2)*a[u] where
# a = AAN_SCALE; the 2-D result is therefore scaled by 8*a[u]*a[v], and the
# quantisation table is pre-multiplied by that factor (verified against a
# reference DCT on impulse and constant blocks during development).
AAN_SCALE = (1.0, 1.387039845, 1.306562965, 1.175875602,
             1.0, 0.785694958, 0.541196100, 0.275899379)

Q_LUM = (
    16, 11, 10, 16, 24, 40, 51, 61,
    12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56,
    14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77,
    24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101,
    72, 92, 95, 98, 112, 100, 103, 99,
)
Q_CHR = (
    17, 18, 24, 47, 99, 99, 99, 99,
    18, 21, 26, 66, 99, 99, 99, 99,
    24, 26, 56, 99, 99, 99, 99, 99,
    47, 66, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
)

ZIGZAG = (
    0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
    12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
    35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51,
    58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63,
)

# (bits, values) per Annex K.3.3
HUFF = {
    ("dc", 0): (
        (0, 1, 5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0),
        (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
    ),
    ("dc", 1): (
        (0, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0),
        (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
    ),
    ("ac", 0): (
        (0, 2, 1, 3, 3, 2, 4, 3, 5, 5, 4, 4, 0, 0, 1, 0x7D),
        (0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41,
         0x06, 0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91,
         0xA1, 0x08, 0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24,
         0x33, 0x62, 0x72, 0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A,
         0x25, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38,
         0x39, 0x3A, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49, 0x4A, 0x53,
         0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5A, 0x63, 0x64, 0x65, 0x66,
         0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79,
         0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89, 0x8A, 0x92, 0x93,
         0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3, 0xA4, 0xA5,
         0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7,
         0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
         0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1,
         0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2,
         0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA),
    ),
    ("ac", 1): (
        (0, 2, 1, 2, 4, 4, 3, 4, 7, 5, 4, 4, 0, 1, 2, 0x77),
        (0x00, 0x01, 0x02, 0x03, 0x11, 0x04, 0x05, 0x21, 0x31, 0x06, 0x12,
         0x41, 0x51, 0x07, 0x61, 0x71, 0x13, 0x22, 0x32, 0x81, 0x08, 0x14,
         0x42, 0x91, 0xA1, 0xB1, 0xC1, 0x09, 0x23, 0x33, 0x52, 0xF0, 0x15,
         0x62, 0x72, 0xD1, 0x0A, 0x16, 0x24, 0x34, 0xE1, 0x25, 0xF1, 0x17,
         0x18, 0x19, 0x1A, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x35, 0x36, 0x37,
         0x38, 0x39, 0x3A, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49, 0x4A,
         0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5A, 0x63, 0x64, 0x65,
         0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78,
         0x79, 0x7A, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89, 0x8A,
         0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
         0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5,
         0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7,
         0xC8, 0xC9, 0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9,
         0xDA, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF2,
         0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA),
    ),
}


def _build_codes(bits, values):
    """Canonical Huffman codes: symbol -> (code, length)."""
    codes = {}
    code = 0
    k = 0
    for length in range(1, 17):
        for _ in range(bits[length - 1]):
            codes[values[k]] = (code, length)
            k += 1
            code += 1
        code <<= 1
    return codes


def _scale_quant(base, quality):
    if quality < 50:
        scale = 5000 // quality
    else:
        scale = 200 - 2 * quality
    out = []
    for v in base:
        q = (v * scale + 50) // 100
        out.append(1 if q < 1 else (255 if q > 255 else q))
    return out


class BitWriter:
    def __init__(self):
        self.buf = bytearray()
        self.acc = 0
        self.nbits = 0

    def write(self, code, length):
        self.acc = (self.acc << length) | code
        self.nbits += length
        while self.nbits >= 8:
            self.nbits -= 8
            byte = (self.acc >> self.nbits) & 0xFF
            self.buf.append(byte)
            if byte == 0xFF:
                self.buf.append(0x00)
        # keep the accumulator small: drop the bits already emitted,
        # otherwise it grows into a multi-megabit int and every shift
        # gets slower as the scan progresses.
        self.acc &= (1 << self.nbits) - 1

    def flush(self):
        if self.nbits:
            pad = 8 - self.nbits
            self.write((1 << pad) - 1, pad)
        return bytes(self.buf)


def _dct1d(f):
    """AAN 1-D DCT on a list of 8 floats; returns 8 scaled outputs."""
    t0 = f[0] + f[7]
    t7 = f[0] - f[7]
    t1 = f[1] + f[6]
    t6 = f[1] - f[6]
    t2 = f[2] + f[5]
    t5 = f[2] - f[5]
    t3 = f[3] + f[4]
    t4 = f[3] - f[4]
    t10 = t0 + t3
    t13 = t0 - t3
    t11 = t1 + t2
    t12 = t1 - t2
    o0 = t10 + t11
    o4 = t10 - t11
    z1 = (t12 + t13) * 0.7071067811865476
    o2 = t13 + z1
    o6 = t13 - z1
    t10 = t4 + t5
    t11 = t5 + t6
    t12 = t6 + t7
    z5 = (t10 - t12) * 0.3826834323650898
    z2 = 0.541196100146197 * t10 + z5
    z4 = 1.3065629648763766 * t12 + z5
    z3 = t11 * 0.7071067811865476
    z11 = t7 + z3
    z13 = t7 - z3
    o5 = z13 + z2
    o3 = z13 - z2
    o1 = z11 + z4
    o7 = z11 - z4
    return (o0, o1, o2, o3, o4, o5, o6, o7)


def encode_jpeg(rgb, w, h, quality=72):
    """Encode raw RGB bytes (w*h*3) as a baseline JPEG (4:2:0)."""
    qlum = _scale_quant(Q_LUM, quality)
    qchr = _scale_quant(Q_CHR, quality)
    # effective quant tables folded with the AAN scale factor 8*a[u]*a[v]
    qeff_l = [0.0] * 64
    qeff_c = [0.0] * 64
    for v in range(8):
        for u in range(8):
            f = 8.0 * AAN_SCALE[u] * AAN_SCALE[v]
            qeff_l[v * 8 + u] = qlum[v * 8 + u] * f
            qeff_c[v * 8 + u] = qchr[v * 8 + u] * f

    dc_lum = _build_codes(*HUFF[("dc", 0)])
    ac_lum = _build_codes(*HUFF[("ac", 0)])
    dc_chr = _build_codes(*HUFF[("dc", 1)])
    ac_chr = _build_codes(*HUFF[("ac", 1)])

    # ---- RGB -> YCbCr planes (integer, scaled by 65536)
    t_yr = [19595 * i for i in range(256)]
    t_yg = [38470 * i for i in range(256)]
    t_yb = [7471 * i for i in range(256)]
    t_cbr = [-11059 * i for i in range(256)]
    t_cbg = [-21709 * i for i in range(256)]
    t_cbb = [32768 * i for i in range(256)]
    t_crr = [32768 * i for i in range(256)]
    t_crg = [-27439 * i for i in range(256)]
    t_crb = [-5329 * i for i in range(256)]
    y_plane = bytearray(w * h)
    cb_half = bytearray((w // 2) * (h // 2))
    cr_half = bytearray((w // 2) * (h // 2))
    px = rgb
    for yy in range(h):
        rowoff = yy * w
        for xx in range(w):
            o = (rowoff + xx) * 3
            r = px[o]
            g = px[o + 1]
            b = px[o + 2]
            y_plane[rowoff + xx] = (t_yr[r] + t_yg[g] + t_yb[b] + 32768) >> 16
        if yy % 2 == 0:
            hy = yy // 2
            for hx in range(w // 2):
                # average the 2x2 block for chroma
                o0 = (rowoff + 2 * hx) * 3
                o1 = o0 + 3
                o2 = o0 + w * 3
                o3 = o2 + 3
                r = (px[o0] + px[o1] + px[o2] + px[o3] + 2) >> 2
                g = (px[o0 + 1] + px[o1 + 1] + px[o2 + 1] + px[o3 + 1] + 2) >> 2
                b = (px[o0 + 2] + px[o1 + 2] + px[o2 + 2] + px[o3 + 2] + 2) >> 2
                idx = hy * (w // 2) + hx
                cb_half[idx] = 128 + ((t_cbr[r] + t_cbg[g] + t_cbb[b] + 32768) >> 16)
                cr_half[idx] = 128 + ((t_crr[r] + t_crg[g] + t_crb[b] + 32768) >> 16)

    bw = BitWriter()
    prev_dc = [0, 0, 0]

    def put_bits(v, size):
        if size == 0:
            return
        if v < 0:
            v += (1 << size) - 1
        bw.write(v, size)

    def encode_block(samples, qeff, dc_tab, ac_tab, comp):
        """samples: 64 level-shifted ints (row-major). Encodes one block."""
        # flat block fast path: only DC is non-zero
        first = samples[0]
        flat = True
        for s in samples:
            if s != first:
                flat = False
                break
        if flat:
            qdc = int(round(64.0 * first / qeff[0]))
        else:
            # 2-D AAN DCT: rows then columns
            rows = []
            for r in range(8):
                base = r * 8
                rows.append(_dct1d([float(samples[base + i]) for i in range(8)]))
            # columns
            q = [0] * 64
            for c in range(8):
                col = _dct1d([rows[r][c] for r in range(8)])
                for r in range(8):
                    v = col[r]
                    if v < 0:
                        qv = -int(round(-v / qeff[r * 8 + c]))
                    else:
                        qv = int(round(v / qeff[r * 8 + c]))
                    q[r * 8 + c] = qv
            qdc = q[0]
        # DC difference
        diff = qdc - prev_dc[comp]
        prev_dc[comp] = qdc
        size = abs(diff).bit_length()
        code, ln = dc_tab[size]
        bw.write(code, ln)
        put_bits(diff, size)
        if flat:
            code, ln = ac_tab[0x00]
            bw.write(code, ln)
            return
        # AC run-length in zigzag order
        run = 0
        for k in range(1, 64):
            v = q[ZIGZAG[k]]
            if v == 0:
                run += 1
                continue
            while run > 15:
                code, ln = ac_tab[0xF0]
                bw.write(code, ln)
                run -= 16
            size = abs(v).bit_length()
            sym = (run << 4) | size
            code, ln = ac_tab[sym]
            bw.write(code, ln)
            put_bits(v, size)
            run = 0
        if run:
            code, ln = ac_tab[0x00]
            bw.write(code, ln)

    # ---- scan: 16x16 MCUs, 4 Y + 1 Cb + 1 Cr per MCU
    for my in range(0, h, 16):
        for mx in range(0, w, 16):
            for by in (0, 8):
                for bx in (0, 8):
                    blk = []
                    for r in range(8):
                        base = (my + by + r) * w + mx + bx
                        blk.extend(y_plane[base:base + 8])
                    blk = [s - 128 for s in blk]
                    encode_block(blk, qeff_l, dc_lum, ac_lum, 0)
            for plane, qeff, dct, act, comp in (
                    (cb_half, qeff_c, dc_chr, ac_chr, 1),
                    (cr_half, qeff_c, dc_chr, ac_chr, 2)):
                blk = []
                hy0 = my // 2
                hx0 = mx // 2
                hw = w // 2
                for r in range(8):
                    base = (hy0 + r) * hw + hx0
                    blk.extend(plane[base:base + 8])
                blk = [s - 128 for s in blk]
                encode_block(blk, qeff, dct, act, comp)

    scan = bw.flush()

    def marker(m):
        return b"\xff" + bytes([m])

    def seg(m, payload):
        return marker(m) + struct.pack(">H", len(payload) + 2) + payload

    out = bytearray()
    out += marker(0xD8)  # SOI
    out += seg(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")  # APP0
    out += seg(0xDB, bytes([0]) + bytes(qlum))   # DQT lum
    out += seg(0xDB, bytes([1]) + bytes(qchr))   # DQT chr
    sof = struct.pack(">BHHB", 8, h, w, 3)
    sof += bytes([1, 0x22, 0, 2, 0x11, 1, 3, 0x11, 1])
    out += seg(0xC0, sof)  # SOF0
    for (cls, tid), (bits, values) in (
            (("dc", 0), HUFF[("dc", 0)]),
            (("ac", 0), HUFF[("ac", 0)]),
            (("dc", 1), HUFF[("dc", 1)]),
            (("ac", 1), HUFF[("ac", 1)])):
        cls_n = 0 if cls == "dc" else 1
        payload = bytes([cls_n << 4 | tid]) + bytes(bits) + bytes(values)
        out += seg(0xC4, payload)  # DHT
    sos = bytes([3, 1, 0x00, 2, 0x11, 3, 0x11, 0, 63, 0])
    out += seg(0xDA, sos)  # SOS
    out += scan
    out += marker(0xD9)  # EOI
    return bytes(out)


# ---------------------------------------------------------------- main
def main():
    cv = build_page()
    data = encode_jpeg(bytes(cv.px), W, H, QUALITY)
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    try:
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "entry.png"), "wb") as f:
            f.write(data)
        print("wrote %s/entry.png %d bytes" % (outdir, len(data)))
    except OSError as exc:
        print("cannot write %s: %s" % (outdir, exc), file=sys.stderr)
        raise
    # best-effort local copy for review; a read-only directory must not
    # fail the run.
    try:
        with open(os.path.join(HERE, "entry.png"), "wb") as f:
            f.write(data)
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
