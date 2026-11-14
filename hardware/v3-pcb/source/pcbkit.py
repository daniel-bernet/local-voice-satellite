# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Daniel Bernet
"""
pcbkit - PCB-as-code toolkit (no KiCad needed to generate; KiCad 9 opens the result)
=====================================================================================
Design frame: millimetres, X right, Y UP (maths frame). Everything is converted to KiCad's
Y-down frame only inside the writers. Footprints are defined as plain pad lists (from datasheets),
instances are pre-rotated by code (footprint rotation is always 0 in the file, so there is no
ambiguity about KiCad's angle convention).

Pipeline: parts + nets -> placement -> grid router (A*, 2 layers) -> zone fills (shapely) ->
DRC (shapely) -> writers (.kicad_pcb / .kicad_sch / .kicad_pro / .pretty) -> Gerbers (own writer)
-> SVG/PNG renders.

Written with AI assistance (see docs/how-it-was-built.md). The DRC here is a geometric check of
the board model, not KiCad's DRC.
"""
import math, uuid, json, os, heapq, itertools
import numpy as np
from shapely.geometry import Polygon, Point, LineString, box as sbox, MultiPolygon
from shapely.ops import unary_union, split

MM = 1.0
LIB = "satellite"          # footprint / symbol library name written into the KiCad files


def uid():
    return str(uuid.uuid4())


def f(x):
    """format a number for s-expressions"""
    s = f"{x:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# ---------------------------------------------------------------------------
# Footprints: pads in local coordinates, Y up. type: "smd" | "tht" | "npth"
# ---------------------------------------------------------------------------
class Pad:
    def __init__(self, name, x, y, w, h, kind="smd", shape="roundrect", drill=None, layer="F", rr=0.25):
        self.name, self.x, self.y, self.w, self.h = str(name), x, y, w, h
        self.kind, self.shape, self.drill, self.layer, self.rr = kind, shape, drill, layer, rr

    def rotated(self, rot):
        r = math.radians(rot)
        x = self.x * math.cos(r) - self.y * math.sin(r)
        y = self.x * math.sin(r) + self.y * math.cos(r)
        w, h = (self.w, self.h) if rot % 180 == 0 else (self.h, self.w)
        return Pad(self.name, x, y, w, h, self.kind, self.shape, self.drill, self.layer, self.rr)


class Footprint:
    def __init__(self, name, pads, courtyard, silk=None, fab=None, desc="", height=1.0, keepout_r=0.0):
        self.name, self.pads, self.courtyard = name, pads, courtyard   # courtyard: (x0,y0,x1,y1)
        self.silk = silk or []       # list of ("line",x0,y0,x1,y1) / ("circle",x,y,r) / ("rect",x0,y0,x1,y1)
        self.fab = fab or []
        self.desc, self.height, self.keepout_r = desc, height, keepout_r

    def rotated(self, rot):
        if rot == 0:
            return self
        r = math.radians(rot)

        def R(x, y):
            return (x * math.cos(r) - y * math.sin(r), x * math.sin(r) + y * math.cos(r))

        pads = [p.rotated(rot) for p in self.pads]
        x0, y0, x1, y1 = self.courtyard
        pts = [R(x0, y0), R(x1, y0), R(x1, y1), R(x0, y1)]
        cy = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))

        def rot_items(items):
            out = []
            for it in items:
                if it[0] == "line":
                    a, b = R(it[1], it[2]), R(it[3], it[4]); out.append(("line", *a, *b))
                elif it[0] == "circle":
                    a = R(it[1], it[2]); out.append(("circle", *a, it[3]))
                elif it[0] == "rect":
                    a, b = R(it[1], it[2]), R(it[3], it[4])
                    out.append(("rect", min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])))
            return out
        return Footprint(self.name, pads, cy, rot_items(self.silk), rot_items(self.fab), self.desc, self.height, self.keepout_r)


def silk_rect(x0, y0, x1, y1):
    return [("rect", x0, y0, x1, y1)]


# ---- generic package generators (IPC-ish, hand-solder friendly: generous pads) ----
def fp_chip(size="0805"):
    dims = {"0603": (1.6, 0.8, 0.9, 0.95, 1.9), "0805": (2.0, 1.25, 1.15, 1.45, 2.4),
            "1206": (3.2, 1.6, 1.15, 1.8, 3.6), "1812": (4.5, 3.2, 1.3, 3.4, 5.1)}
    L, W, pw, ph, pc = dims[size]
    pads = [Pad(1, -pc / 2, 0, pw, ph), Pad(2, pc / 2, 0, pw, ph)]
    cx = pads[1].x + pw / 2 + 0.25
    cy = ph / 2 + 0.25
    silk = [("line", -L / 2 + 0.2, cy + 0.05, L / 2 - 0.2, cy + 0.05), ("line", -L / 2 + 0.2, -cy - 0.05, L / 2 - 0.2, -cy - 0.05)]
    return Footprint(f"C_{size}", pads, (-cx, -cy, cx, cy), silk, [("rect", -L / 2, -W / 2, L / 2, W / 2)], f"{size} chip", 0.8)


def fp_sma():
    """DO-214AC (SMA) diode, pad 1 = cathode (band)"""
    pads = [Pad(1, -2.3, 0, 2.5, 1.8), Pad(2, 2.3, 0, 2.5, 1.8)]
    silk = [("line", -3.7, 1.4, 1.2, 1.4), ("line", -3.7, -1.4, 1.2, -1.4), ("line", -3.7, -1.4, -3.7, 1.4)]
    return Footprint("D_SMA", pads, (-3.8, -1.5, 3.8, 1.5), silk, [("rect", -2.15, -1.3, 2.15, 1.3)], "SMA diode", 2.3)


def fp_sot223():
    """SOT-223: pins 1,2,3 (pitch 2.3) + tab (pin 4 = pin 2)"""
    pads = [Pad(1, -2.3, -3.3, 1.2, 2.0), Pad(2, 0, -3.3, 1.2, 2.0), Pad(3, 2.3, -3.3, 1.2, 2.0), Pad(2, 0, 3.3, 3.4, 2.0)]
    silk = [("line", -3.4, 1.9, 3.4, 1.9), ("line", -3.4, -1.9, 3.4, -1.9), ("line", -3.4, -1.9, -3.4, 1.9), ("line", 3.4, -1.9, 3.4, 1.9)]
    return Footprint("SOT-223", pads, (-3.6, -4.5, 3.6, 4.5), silk, [("rect", -3.3, -1.8, 3.3, 1.8)], "SOT-223", 1.8)


def fp_sot23(n=5):
    """SOT-23-5 / SOT-23-6, 0.95 pitch, pins 1..3 bottom (left->right), 4..n top (right->left)"""
    pads = []
    xs = [-0.95, 0, 0.95]
    for i, x in enumerate(xs):
        pads.append(Pad(i + 1, x, -1.3, 0.6, 1.1))
    top = [0.95, -0.95] if n == 5 else [0.95, 0, -0.95]
    for i, x in enumerate(top):
        pads.append(Pad(4 + i, x, 1.3, 0.6, 1.1))
    silk = [("line", -1.6, 0.9, 1.6, 0.9), ("line", -1.6, -0.9, 1.6, -0.9)]
    return Footprint(f"SOT-23-{n}", pads, (-1.8, -2.0, 1.8, 2.0), silk, [("rect", -1.5, -0.8, 1.5, 0.8)], f"SOT-23-{n}", 1.1)


def fp_tqfn16_3x3(ep=1.6, back_hole=True):
    """TQFN-16 3x3 mm, 0.5 pitch, pin 1 at top-left going down the left side (CCW). Exposed pad with an
    optional 1.0 mm plated hole so the EP can be soldered from the back with an iron."""
    pads = []
    pos = [-0.75, -0.25, 0.25, 0.75]
    for i, y in enumerate(pos):              # left side pins 1-4, top to bottom
        pads.append(Pad(i + 1, -1.45, -y, 0.9, 0.28))
    for i, x in enumerate(pos):              # bottom 5-8 left to right
        pads.append(Pad(5 + i, x, -1.45, 0.28, 0.9))
    for i, y in enumerate(pos):              # right 9-12 bottom to top
        pads.append(Pad(9 + i, 1.45, y, 0.9, 0.28))
    for i, x in enumerate(pos):              # top 13-16 right to left
        pads.append(Pad(13 + i, -x, 1.45, 0.28, 0.9))
    pads.append(Pad(17, 0, 0, ep, ep, shape="rect"))
    if back_hole:
        pads.append(Pad(17, 0, 0, 1.6, 1.6, kind="tht", shape="circle", drill=1.0))
    silk = [("circle", -1.9, 1.9, 0.15)]
    return Footprint("TQFN-16_3x3", pads, (-2.1, -2.1, 2.1, 2.1), silk, [("rect", -1.5, -1.5, 1.5, 1.5)], "TQFN-16 3x3 P0.5", 0.8)


def fp_radial(d=8.0, pitch=3.5, drill=1.0):
    """THT radial electrolytic, pin 1 = + (square)"""
    pads = [Pad(1, -pitch / 2, 0, 1.8, 1.8, "tht", "rect", drill), Pad(2, pitch / 2, 0, 1.8, 1.8, "tht", "circle", drill)]
    r = d / 2 + 0.3
    silk = [("circle", 0, 0, r), ("line", -r - 1.2, 0.6, -r - 1.2, -0.6)]   # bar on the + side
    return Footprint(f"CP_Radial_D{d}", pads, (-r - 0.3, -r - 0.3, r + 0.3, r + 0.3), silk, [("circle", 0, 0, d / 2)], f"radial cap D{d} P{pitch}", 12.0)


def fp_jst_ph(n):
    """JST PH 2.0 mm top-entry THT header (B{n}B-PH-K-S). Pin 1 at -x."""
    pads = [Pad(i + 1, (i - (n - 1) / 2) * 2.0, 0, 1.2, 1.7, "tht", "rect" if i == 0 else "oval", 0.75) for i in range(n)]
    w = (n - 1) * 2.0 + 3.9
    silk = [("rect", -w / 2, -1.7 - 0.2, w / 2, 1.7 + 0.2 + 1.0)]
    return Footprint(f"JST_PH_B{n}B", pads, (-w / 2 - 0.3, -2.3, w / 2 + 0.3, 3.3), silk, [], f"JST PH {n}p", 6.0)


def fp_header(n, pitch=2.54):
    pads = [Pad(i + 1, (i - (n - 1) / 2) * pitch, 0, 1.7, 1.7, "tht", "rect" if i == 0 else "circle", 1.0) for i in range(n)]
    w = n * pitch
    return Footprint(f"PinHeader_1x{n:02d}", pads, (-w / 2 - 0.3, -1.6, w / 2 + 0.3, 1.6), silk_rect(-w / 2, -1.27, w / 2, 1.27), [], f"1x{n} 2.54 header", 8.5)


def fp_tact_6x6():
    """6x6 mm THT tactile switch, 4 legs (pins 1/2 = one contact, 3/4 = other)"""
    pads = [Pad(1, -3.25, 2.25, 1.9, 1.9, "tht", "rect", 1.1), Pad(1, 3.25, 2.25, 1.9, 1.9, "tht", "circle", 1.1),
            Pad(2, -3.25, -2.25, 1.9, 1.9, "tht", "circle", 1.1), Pad(2, 3.25, -2.25, 1.9, 1.9, "tht", "circle", 1.1)]
    return Footprint("SW_Tact_6x6", pads, (-3.6, -3.6, 3.6, 3.6), silk_rect(-3.1, -3.1, 3.1, 3.1), [("circle", 0, 0, 1.75)], "6x6 tact THT", 5.0)


def fp_ws2812b():
    """WS2812B 5050, 4 pads 3.2 x 1.5 at +-2.45 x, +-1.6 y. Pins: 1 VDD, 2 DOUT, 3 GND, 4 DIN (pin1 marked corner, cut)"""
    pads = [Pad(1, -2.45, 1.6, 1.5, 1.0), Pad(2, -2.45, -1.6, 1.5, 1.0), Pad(3, 2.45, -1.6, 1.5, 1.0), Pad(4, 2.45, 1.6, 1.5, 1.0)]
    silk = [("line", -2.6, 2.6, 2.6, 2.6), ("line", -2.6, -2.6, 2.6, -2.6), ("line", -3.3, 2.0, -3.3, 2.8), ("line", -3.3, 2.8, -2.6, 2.8)]
    return Footprint("LED_WS2812B_5050", pads, (-3.5, -2.9, 3.5, 2.9), silk, [("rect", -2.5, -2.5, 2.5, 2.5)], "WS2812B 5050", 1.6)


def fp_solder_jumper3():
    """3-pad solder jumper (1 - C - 2), pads 1.0 x 1.5 at 1.3 pitch"""
    pads = [Pad(1, -1.3, 0, 1.0, 1.5, rr=0.1), Pad(2, 0, 0, 1.0, 1.5, rr=0.1), Pad(3, 1.3, 0, 1.0, 1.5, rr=0.1)]
    return Footprint("SolderJumper_3", pads, (-2.0, -1.1, 2.0, 1.1), silk_rect(-1.95, -1.05, 1.95, 1.05), [], "solder jumper 3", 0.1)


def fp_mounting_hole(d=3.2, pad=6.4):
    pads = [Pad(1, 0, 0, pad, pad, "npth", "circle", d)]
    return Footprint(f"MountingHole_{d}", pads, (-pad / 2 - 0.2, -pad / 2 - 0.2, pad / 2 + 0.2, pad / 2 + 0.2), [("circle", 0, 0, pad / 2 + 0.1)], [], "mounting hole", 0.0, keepout_r=pad / 2)


def fp_esp32s3_wroom1():
    """ESP32-S3-WROOM-1: 18 x 25.5 mm body; antenna end at +y, overhanging the board edge.
    Pads 0.9 x 1.5 (castellated, straddling the edges), pitch 1.27. Pins 1-14 left (top->bottom),
    15-26 bottom (left->right), 27-40 right (bottom->top), 41 = EPAD (3x3 grid of 0.9 pads + back hole).
    Origin = module centre. Geometry from the Espressif datasheet / qeda library; VERIFY against KiCad's
    RF_Module:ESP32-S3-WROOM-1 before ordering (swap footprint in KiCad, nets stay)."""
    pads = []
    # qeda frame: antenna at -y, column centred at y=+2.995. Our frame: antenna at +y -> flip y.
    for i in range(14):
        yq = 2.995 + (i - 6.5) * 1.27        # pin 1 at the top (nearest antenna) in qeda frame = smallest yq
        pads.append(Pad(i + 1, -8.75, -yq, 1.5, 0.9))
    for i in range(12):
        xq = (i - 5.5) * 1.27
        pads.append(Pad(15 + i, xq, -12.5, 0.9, 1.5))
    for i in range(14):
        yq = 2.995 + (13 - i - 6.5) * 1.27   # pin 27 at the bottom right, going up
        pads.append(Pad(27 + i, 8.75, -yq, 1.5, 0.9))
    for j in range(3):
        for i in range(3):
            pads.append(Pad(41, (i - 1) * 1.4, -2.995 + (j - 1) * 1.4, 0.9, 0.9, shape="rect"))
    pads.append(Pad(41, 0, -2.995, 2.6, 2.6, kind="tht", shape="circle", drill=1.8))   # back-solder hole for the EPAD
    silk = [("rect", -9.0, -12.75, 9.0, 12.75), ("line", -9.0, 6.75, 9.0, 6.75)]       # antenna area above the line
    fab = [("rect", -9.0, -12.75, 9.0, 12.75)]
    return Footprint("ESP32-S3-WROOM-1", pads, (-9.3, -13.05, 9.3, 13.05), silk, fab, "ESP32-S3-WROOM-1 module", 3.2)


def fp_usb4085():
    """GCT USB4085-GF-A: USB-C 2.0 receptacle, 16 THT pins + 4 THT shell stakes. Geometry re-created from
    the datasheet / KiCad library numbers (0.85 pitch, rows 1.35 apart). Local frame: +y = towards the mating
    face (board edge). Row A at y=0, row B at y=1.35, PCB edge at y=6.1 (ESTIMATE), front face at y=8.61.
    Origin x = centre of the pin rows."""
    pads = []
    xa = {"A1": 0, "A4": 0.85, "A5": 1.7, "A6": 2.55, "A7": 3.4, "A8": 4.25, "A9": 5.1, "A12": 5.95}
    xb = {"B12": 0, "B9": 0.85, "B8": 1.7, "B7": 2.55, "B6": 3.4, "B5": 4.25, "B4": 5.1, "B1": 5.95}
    cx = 2.975
    for n, x in xa.items():
        pads.append(Pad(n, x - cx, 0, 0.7, 0.7, "tht", "circle", 0.4))
    for n, x in xb.items():
        pads.append(Pad(n, x - cx, 1.35, 0.7, 0.7, "tht", "circle", 0.4))
    for sx in (-1.35, 7.3):
        pads.append(Pad("S1", sx - cx, 0.98, 0.9, 2.4, "tht", "oval", (0.6, 2.1)))    # slot 0.6 x 2.1
        pads.append(Pad("S1", sx - cx, 4.36, 0.9, 1.7, "tht", "oval", (0.6, 1.4)))    # slot 0.6 x 1.4
    silk = [("line", -1.62 - cx, -0.68, 7.57 - cx, -0.68), ("line", -1.62 - cx, -0.68, -1.62 - cx, 6.0), ("line", 7.57 - cx, -0.68, 7.57 - cx, 6.0)]
    fab = [("rect", -1.5 - cx, -0.56, 7.45 - cx, 8.61)]
    return Footprint("USB_C_GCT_USB4085", pads, (-2.3 - cx, -1.06, 8.25 - cx, 9.11), silk, fab, "GCT USB4085-GF-A USB-C THT", 3.46)


def fp_wire_pad(w=3.0, h=2.5):
    """large SMD solder pad for a wire end (no hole -> airtight)"""
    return Footprint(f"WirePad_{w}x{h}", [Pad(1, 0, 0, w, h, rr=0.15)], (-w / 2 - 0.3, -h / 2 - 0.3, w / 2 + 0.3, h / 2 + 0.3), silk_rect(-w / 2 - 0.2, -h / 2 - 0.2, w / 2 + 0.2, h / 2 + 0.2), [], "wire solder pad", 0.1)


def fp_mic_module_2x3(row_pitch=8.0):
    """INMP441 / ICS-43434 round module (D14): two rows of 3 header pins, 2.54 pitch, rows row_pitch apart,
    plus a 2.5 mm sound-port hole at the centre. Pin numbering: row A (x<0) 1-3 bottom->top, row B 4-6."""
    pads = []
    for i, y in enumerate((-2.54, 0, 2.54)):
        pads.append(Pad(i + 1, -row_pitch / 2, y, 1.7, 1.7, "tht", "rect" if i == 0 else "circle", 1.0))
    for i, y in enumerate((-2.54, 0, 2.54)):
        pads.append(Pad(4 + i, row_pitch / 2, y, 1.7, 1.7, "tht", "circle", 1.0))
    pads.append(Pad("", 0, 0, 2.5, 2.5, "npth", "circle", 2.5))
    return Footprint("MIC_Module_D14_2x3", pads, (-7.3, -7.3, 7.3, 7.3), [("circle", 0, 0, 7.1)], [("circle", 0, 0, 7.0)], "round I2S mic module", 3.0, keepout_r=1.25)


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------
class Part:
    def __init__(self, ref, fp, x, y, rot, value, nets, layer="F", dnp=False, mfr="", lcsc=""):
        self.ref, self.fp0, self.x, self.y, self.rot, self.value = ref, fp, x, y, rot, value
        self.fp = fp.rotated(rot)
        self.nets = nets                      # {pad name: net name}
        self.layer, self.dnp, self.mfr, self.lcsc = layer, dnp, mfr, lcsc

    def pads(self):
        for p in self.fp.pads:
            yield p, (self.x + p.x, self.y + p.y), self.nets.get(p.name)

    def courtyard(self):
        x0, y0, x1, y1 = self.fp.courtyard
        return sbox(self.x + x0, self.y + y0, self.x + x1, self.y + y1)


class Board:
    def __init__(self, name, w, d, r=5.0, thickness=1.6):
        self.name, self.w, self.d, self.r, self.thickness = name, w, d, r, thickness
        self.parts = {}
        self.tracks = []          # (layer, [(x,y),...], width, net)
        self.vias = []            # (x, y, net, size, drill)
        self.zones = []           # dict(layer, net, polygon(shapely), priority, fills[list of simple polys])
        self.keepouts = []        # shapely polygons (both layers, no copper)
        self.texts = []           # (layer, x, y, text, size, rot)
        self.gr_lines = []        # (layer, x0,y0,x1,y1, width)
        self.net_classes = {}     # net -> width
        self.outline = self._outline_poly()

    def _outline_poly(self):
        return sbox(0, 0, self.w, self.d).buffer(-self.r).buffer(self.r, join_style=1, resolution=16)

    def add(self, part):
        assert part.ref not in self.parts, part.ref
        self.parts[part.ref] = part
        return part

    def nets(self):
        ns = set()
        for p in self.parts.values():
            ns.update(n for n in p.nets.values() if n)
        return sorted(ns)

    # --- geometry helpers ------------------------------------------------------
    def pad_poly(self, pad, pos):
        x, y = pos
        if pad.shape == "circle":
            return Point(x, y).buffer(pad.w / 2, resolution=12)
        if pad.shape == "oval":
            r = min(pad.w, pad.h) / 2
            return sbox(x - pad.w / 2 + r, y - pad.h / 2 + r, x + pad.w / 2 - r, y + pad.h / 2 - r).buffer(r, resolution=8)
        if pad.shape == "roundrect":
            rr = min(pad.w, pad.h) * pad.rr
            return sbox(x - pad.w / 2 + rr, y - pad.h / 2 + rr, x + pad.w / 2 - rr, y + pad.h / 2 - rr).buffer(rr, resolution=6, join_style=1)
        return sbox(x - pad.w / 2, y - pad.h / 2, x + pad.w / 2, y + pad.h / 2)

    def copper(self, layer, net=None, exclude_zones=False):
        """union of copper on a layer (F/B), optionally for one net only (net=None -> all)"""
        geoms = []
        for part in self.parts.values():
            for pad, pos, n in part.pads():
                if pad.kind == "npth":
                    continue
                on = pad.kind == "tht" or pad.layer == layer
                if on and (net is None or n == net):
                    geoms.append(self.pad_poly(pad, pos))
        for (lay, pts, w, n) in self.tracks:
            if lay == layer and (net is None or n == net):
                geoms.append(LineString(pts).buffer(w / 2, resolution=8))
        for (x, y, n, s, dr) in self.vias:
            if net is None or n == net:
                geoms.append(Point(x, y).buffer(s / 2, resolution=12))
        if not exclude_zones:
            for z in self.zones:
                if z["layer"] == layer and (net is None or z["net"] == net):
                    geoms.extend(z.get("fills", []))
        return unary_union(geoms) if geoms else Polygon()

    def holes(self):
        out = []
        for part in self.parts.values():
            for pad, pos, n in part.pads():
                if pad.kind in ("tht", "npth"):
                    out.append((pos, pad.drill[0] if isinstance(pad.drill, tuple) else pad.drill, pad.kind == "tht"))
        for (x, y, n, s, dr) in self.vias:
            out.append(((x, y), dr, True))
        for (xh, yh, dh) in getattr(self, "extra_npth", []):
            out.append(((xh, yh), dh, False))
        return out

    # --- zones ---------------------------------------------------------------------
    def fill_zones(self, clearance=0.25, thermal_pads=True, min_width=0.25):
        """compute filled polygons for every zone: zone poly - (other-net copper + clearance) - holes -
        keep-outs - edge clearance. GND THT pads get 4 thermal spokes (easier hand soldering)."""
        for z in self.zones:
            lay, net = z["layer"], z["net"]
            poly = z["poly"].intersection(self.outline.buffer(-0.4))
            blockers = []
            for part in self.parts.values():
                for pad, pos, n in part.pads():
                    on = pad.kind in ("tht", "npth") or pad.layer == lay
                    if not on:
                        continue
                    pp = self.pad_poly(pad, pos)
                    if pad.kind == "npth":
                        blockers.append(pp.buffer(clearance + 0.2))
                    elif n != net:
                        blockers.append(pp.buffer(clearance))
                    elif thermal_pads and pad.kind == "tht":
                        # thermal relief: ring gap minus 4 spokes
                        ring = pp.buffer(clearance + 0.2).difference(pp)
                        spokes = unary_union([sbox(pos[0] - 0.3, pos[1] - 5, pos[0] + 0.3, pos[1] + 5),
                                              sbox(pos[0] - 5, pos[1] - 0.3, pos[0] + 5, pos[1] + 0.3)])
                        blockers.append(ring.difference(spokes))
            for (l2, pts, w, n) in self.tracks:
                if l2 == lay and n != net:
                    blockers.append(LineString(pts).buffer(w / 2 + clearance, resolution=8))
            for (x, y, n, s, dr) in self.vias:
                if n != net:
                    blockers.append(Point(x, y).buffer(s / 2 + clearance, resolution=12))
            for ko in self.keepouts:
                blockers.append(ko)
            for z2 in self.zones:
                if z2 is not z and z2["layer"] == lay and z2["priority"] > z["priority"]:
                    blockers.append(z2["poly"].buffer(clearance))
            fill = poly.difference(unary_union(blockers)) if blockers else poly
            # remove slivers thinner than min_width
            fill = fill.buffer(-min_width / 2).buffer(min_width / 2)
            pieces = []
            geoms = list(fill.geoms) if isinstance(fill, MultiPolygon) else ([fill] if not fill.is_empty else [])
            for g in geoms:
                if g.area < 2.0:
                    continue
                pieces.extend(fracture(g))
            z["fills"] = pieces

    # --- connectivity -------------------------------------------------------------
    def connectivity_report(self):
        """for every net: number of connected islands (should be 1)"""
        report = {}
        for net in self.nets():
            cf = self.copper("F", net)
            cb = self.copper("B", net)
            # link F and B through vias and tht pads
            links = [Point(x, y).buffer(s / 2) for (x, y, n, s, dr) in self.vias if n == net]
            for part in self.parts.values():
                for pad, pos, n in part.pads():
                    if n == net and pad.kind == "tht":
                        links.append(self.pad_poly(pad, pos))
            # graph of pieces
            pieces = []
            for g in _geoms(cf):
                pieces.append(("F", g))
            for g in _geoms(cb):
                pieces.append(("B", g))
            n = len(pieces)
            parent = list(range(n))

            def find(a):
                while parent[a] != a:
                    parent[a] = parent[parent[a]]; a = parent[a]
                return a
            for lnk in links:
                touching = [i for i, (l, g) in enumerate(pieces) if g.intersects(lnk)]
                for i in touching[1:]:
                    parent[find(i)] = find(touching[0])
            islands = len({find(i) for i in range(n)})
            pads = sum(1 for part in self.parts.values() for pad, pos, nn in part.pads() if nn == net)
            report[net] = (islands, pads)
        return report


def _geoms(g):
    if g.is_empty:
        return []
    return list(g.geoms) if hasattr(g, "geoms") else [g]


def fracture(poly):
    """split a polygon with holes into simple polygons by horizontal cuts through each hole (zero gap,
    the pieces share edges -> identical copper after union; KiCad refills zones anyway)"""
    if not poly.interiors:
        return [poly]
    hole = max(poly.interiors, key=lambda r: Polygon(r).area)
    cy = Polygon(hole).centroid.y
    minx, miny, maxx, maxy = poly.bounds
    cut = LineString([(minx - 1, cy), (maxx + 1, cy)])
    out = []
    try:
        parts = split(poly, cut)
    except Exception:
        return [Polygon(poly.exterior)]
    for p in parts.geoms:
        if p.area > 0.01:
            out.extend(fracture(p))
    return out


# ---------------------------------------------------------------------------
# Grid router (A*, two layers, per-net width, vias allowed)
# ---------------------------------------------------------------------------
class Router:
    def __init__(self, board, grid=0.25, clearance=0.25, via_size=0.6, via_drill=0.3, edge_clear=0.5):
        self.b, self.g, self.clr = board, grid, clearance
        self.via_size, self.via_drill = via_size, via_drill
        bx0, by0, bx1, by1 = board.outline.bounds
        self.nx, self.ny = int(bx1 / grid) + 2, int(by1 / grid) + 2
        # occupancy: per layer, net id of the copper occupying the cell (-1 free, -2 blocked for all)
        self.occ = {"F": np.full((self.nx, self.ny), -1, dtype=np.int32), "B": np.full((self.nx, self.ny), -1, dtype=np.int32)}
        self.padcell = {"F": np.zeros((self.nx, self.ny), dtype=bool), "B": np.zeros((self.nx, self.ny), dtype=bool)}
        self.netid = {n: i for i, n in enumerate(board.nets())}
        edge = board.outline.buffer(-edge_clear)
        for ix in range(self.nx):
            for iy in range(self.ny):
                if not edge.contains(Point(ix * grid, iy * grid)):
                    self.occ["F"][ix, iy] = -2; self.occ["B"][ix, iy] = -2
        self.log = []

    def cells(self, geom):
        minx, miny, maxx, maxy = geom.bounds
        ix0, ix1 = max(0, int(minx / self.g) - 1), min(self.nx - 1, int(maxx / self.g) + 1)
        iy0, iy1 = max(0, int(miny / self.g) - 1), min(self.ny - 1, int(maxy / self.g) + 1)
        prep = geom
        out = []
        for ix in range(ix0, ix1 + 1):
            for iy in range(iy0, iy1 + 1):
                if prep.intersects(Point(ix * self.g, iy * self.g)):
                    out.append((ix, iy))
        return out

    def block(self, layer, geom, net, extra=0.0, is_pad=False):
        """mark cells covered by the copper (+ a small margin so grid sampling never under-estimates it)
        as owned by net (or -2 = blocked for every net). Clearance is enforced by the window test in
        route(), not here."""
        nid = self.netid.get(net, -2) if net else -2
        for (ix, iy) in self.cells(geom.buffer(0.05 + extra)):
            cur = self.occ[layer][ix, iy]
            if cur == -1 or nid == -2:
                self.occ[layer][ix, iy] = nid
            if is_pad:
                self.padcell[layer][ix, iy] = True

    def seed_from_board(self, keepout_vias=None):
        b = self.b
        for part in b.parts.values():
            for pad, pos, net in part.pads():
                pp = b.pad_poly(pad, pos)
                if pad.kind == "npth":
                    self.block("F", pp, None, 0.0); self.block("B", pp, None, 0.0)
                elif pad.kind == "tht":
                    self.block("F", pp, net, is_pad=True); self.block("B", pp, net, is_pad=True)
                else:
                    self.block(pad.layer, pp, net, is_pad=True)
        for (lay, pts, w, net) in b.tracks:
            self.block(lay, LineString(pts).buffer(w / 2), net)
        for (x, y, net, s, dr) in b.vias:
            self.block("F", Point(x, y).buffer(s / 2), net); self.block("B", Point(x, y).buffer(s / 2), net)
        for ko in b.keepouts:
            self.block("F", ko, None); self.block("B", ko, None)
        self.no_via = np.zeros((self.nx, self.ny), dtype=bool)
        for (x, y, net, s, dr) in b.vias:
            for c in self.cells(Point(x, y).buffer(0.8)):
                self.no_via[c] = True
        for part in b.parts.values():
            for pad, pos, net in part.pads():
                if pad.kind in ("tht", "npth"):
                    dr = max(pad.drill) if isinstance(pad.drill, tuple) else pad.drill
                    for c in self.cells(Point(pos).buffer(dr / 2 + 0.6)):
                        self.no_via[c] = True
        for ko in (keepout_vias or []):
            for c in self.cells(ko):
                self.no_via[c] = True
        for part in b.parts.values():           # no vias under SMD pads of other nets / inside courtyards of modules
            for pad, pos, net in part.pads():
                for c in self.cells(b.pad_poly(pad, pos).buffer(0.2)):
                    self.no_via[c] = True

    def route(self, net, a, b_, width, layer_pref="F", via_cost=12.0, max_iter=400000, allow_layers=("F", "B"), bend_cost=0.3, goal_layers=None):
        """A* from point a to point b (mm) for net; returns True and commits tracks/vias"""
        nid = self.netid[net]
        g = self.g
        wcells = int(math.ceil((width / 2 + self.clr) / g))     # half-width in cells for occupancy test
        wc_own = int(math.ceil((width / 2) / g))

        def free(layer, ix, iy):
            arr = self.occ[layer]
            x0, x1 = max(0, ix - wcells), min(self.nx - 1, ix + wcells)
            y0, y1 = max(0, iy - wcells), min(self.ny - 1, iy + wcells)
            sub = arr[x0:x1 + 1, y0:y1 + 1]
            return bool(np.all((sub == -1) | (sub == nid)))

        def near_own(layer, ix, iy):
            # only cells inside this net's own pads bypass the clearance window (entering/leaving a pad)
            return self.occ[layer][ix, iy] == nid and self.padcell[layer][ix, iy]

        sa = (int(round(a[0] / g)), int(round(a[1] / g)))
        sb = (int(round(b_[0] / g)), int(round(b_[1] / g)))
        layers = list(allow_layers)
        li = {l: i for i, l in enumerate(layers)}
        start = (sa[0], sa[1], li.get(layer_pref, 0))
        goals = {(sb[0], sb[1], li[l]) for l in layers if (goal_layers is None or l in goal_layers)}

        def h(n):
            return (abs(n[0] - sb[0]) + abs(n[1] - sb[1])) * 0.98

        openq = [(h(start), 0.0, start, None)]
        came, cost = {}, {start: 0.0}
        found = None
        it = 0
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        while openq and it < max_iter:
            it += 1
            fsc, c, n, prev = heapq.heappop(openq)
            if n in came and came[n] is not None and cost.get(n, 1e9) < c - 1e-9:
                continue
            came.setdefault(n, prev)
            if n in goals:
                found = n; break
            x, y, l = n
            lay = layers[l]
            # moves
            for (dx, dy) in dirs:
                nx_, ny_ = x + dx, y + dy
                if not (0 <= nx_ < self.nx and 0 <= ny_ < self.ny):
                    continue
                m = (nx_, ny_, l)
                # cells near own copper are fine, otherwise require free
                if not (near_own(lay, nx_, ny_) or free(lay, nx_, ny_)):
                    continue
                step = 1.414 if dx and dy else 1.0
                # prefer horizontal on F, vertical on B
                if lay == "F" and dy and not dx:
                    step += 0.15
                if lay == "B" and dx and not dy:
                    step += 0.15
                # bend penalty
                if prev is not None:
                    pdx, pdy = x - prev[0], y - prev[1]
                    if (pdx, pdy) != (dx, dy) and prev[2] == l:
                        step += bend_cost
                nc = c + step
                if nc < cost.get(m, 1e18):
                    cost[m] = nc
                    heapq.heappush(openq, (nc + h(m), nc, m, n))
            # via
            if len(layers) > 1 and not self.no_via[x, y]:
                for l2 in range(len(layers)):
                    if l2 == l:
                        continue
                    lay2 = layers[l2]
                    vcells = int(math.ceil((self.via_size / 2 + self.clr) / g))
                    ok = True
                    for L in (lay, lay2):
                        arr = self.occ[L]
                        sub = arr[max(0, x - vcells):x + vcells + 1, max(0, y - vcells):y + vcells + 1]
                        if not np.all((sub == -1) | (sub == nid)):
                            ok = False; break
                    if not ok:
                        continue
                    m = (x, y, l2)
                    nc = c + via_cost
                    if nc < cost.get(m, 1e18):
                        cost[m] = nc
                        heapq.heappush(openq, (nc + h(m), nc, m, n))
        if found is None:
            self.log.append(f"FAILED {net}: {a} -> {b_} after {it} iterations")
            return False
        # reconstruct
        path = []
        n = found
        while n is not None:
            path.append(n); n = came.get(n)
        path.reverse()
        # commit: split into layer runs
        runs = []
        cur = [path[0]]
        for p in path[1:]:
            if p[2] != cur[-1][2]:
                runs.append(cur); cur = [p]
            else:
                cur.append(p)
        runs.append(cur)
        for i, run in enumerate(runs):
            lay = layers[run[0][2]]
            pts = simplify_path([(p[0] * g, p[1] * g) for p in run])
            if len(pts) >= 2:
                self.b.tracks.append((lay, pts, width, net))
                self.block(lay, LineString(pts).buffer(width / 2), net)
            if i < len(runs) - 1:
                vx, vy = run[-1][0] * g, run[-1][1] * g
                self.b.vias.append((vx, vy, net, self.via_size, self.via_drill))
                for L in layers:
                    self.block(L, Point(vx, vy).buffer(self.via_size / 2), net)
                ix, iy = run[-1][0], run[-1][1]
                self.no_via[max(0, ix - 3):ix + 4, max(0, iy - 3):iy + 4] = True
        return True

    def route_net(self, net, points, width, **kw):
        """connect a list of (x,y,layer) pad points with a nearest-neighbour MST order"""
        if len(points) < 2:
            return True
        done = [points[0]]
        rest = list(points[1:])
        ok = True
        while rest:
            best = min(((d2(p, q), p, q) for p in done for q in rest), key=lambda t: t[0])
            _, p, q = best
            lp = p[2] if len(p) > 2 and p[2] in ("F", "B") else kw.get("layer_pref", "F")
            gl = (q[2],) if len(q) > 2 and q[2] in ("F", "B") else None
            r = self.route(net, (p[0], p[1]), (q[0], q[1]), width, layer_pref=lp, goal_layers=gl,
                           **{k: v for k, v in kw.items() if k not in ("layer_pref", "goal_layers")})
            ok = ok and r
            done.append(q); rest.remove(q)
        return ok


def d2(p, q):
    return (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2


def simplify_path(pts):
    """drop collinear points"""
    if len(pts) <= 2:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = out[-1], pts[i], pts[i + 1]
        if abs((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])) > 1e-9:
            out.append(b)
    out.append(pts[-1])
    return out


# ---------------------------------------------------------------------------
# DRC (independent of the router: pure geometry)
# ---------------------------------------------------------------------------
def drc(board, clearance=0.2, edge_clear=0.3, min_drill=0.3, min_annular=0.15, hole_to_hole=0.25):
    errs = []
    nets = board.nets()
    for lay in ("F", "B"):
        per = {n: board.copper(lay, n) for n in nets}
        for a, b_ in itertools.combinations(nets, 2):
            ga, gb = per[a], per[b_]
            if ga.is_empty or gb.is_empty:
                continue
            if ga.distance(gb) < clearance - 1e-6:
                d = ga.distance(gb)
                pt = ga.buffer(d / 2 + 0.01).intersection(gb.buffer(d / 2 + 0.01)).representative_point()
                errs.append(f"clearance {lay} {a} <-> {b_}: {d:.3f} mm at ({pt.x:.1f},{pt.y:.1f})")
        allc = board.copper(lay)
        if not allc.is_empty:
            edge = board.outline.exterior
            dmin = allc.distance(edge)
            if dmin < edge_clear - 1e-6:
                errs.append(f"copper to edge {lay}: {dmin:.3f} mm")
    hs = board.holes()
    for ((x, y), dr, plated) in hs:
        if plated and dr < min_drill - 1e-6:
            errs.append(f"drill {dr} < {min_drill} at ({x:.1f},{y:.1f})")
    for (p1, d1, _), (p2, dd2, _) in itertools.combinations(hs, 2):
        g = math.hypot(p1[0] - p2[0], p1[1] - p2[1]) - d1 / 2 - dd2 / 2
        if g < hole_to_hole - 1e-6:
            errs.append(f"hole-to-hole {g:.2f} at ({p1[0]:.1f},{p1[1]:.1f})")
    for (x, y, n, s, dr) in board.vias:
        if (s - dr) / 2 < min_annular - 1e-6:
            errs.append(f"via annular ring {(s - dr) / 2:.3f} at ({x:.1f},{y:.1f})")
    # courtyards
    parts = list(board.parts.values())
    for a, b_ in itertools.combinations(parts, 2):
        if a.courtyard().intersects(b_.courtyard()) and a.courtyard().intersection(b_.courtyard()).area > 0.01:
            errs.append(f"courtyard overlap {a.ref} <-> {b_.ref}")
    # outline
    for p in parts:
        if not board.outline.contains(p.courtyard()) and not getattr(p.fp0, "may_overhang", False):
            errs.append(f"courtyard outside outline: {p.ref}")
    # connectivity
    for net, (isl, npads) in board.connectivity_report().items():
        if isl > 1:
            errs.append(f"net {net}: {isl} islands (unrouted)")
    return errs


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------
LAYERS_V9 = [(0, "F.Cu", "signal"), (2, "B.Cu", "signal"), (9, "F.Adhes", "user", "F.Adhesive"), (11, "B.Adhes", "user", "B.Adhesive"),
             (13, "F.Paste", "user"), (15, "B.Paste", "user"), (5, "F.SilkS", "user", "F.Silkscreen"), (7, "B.SilkS", "user", "B.Silkscreen"),
             (1, "F.Mask", "user"), (3, "B.Mask", "user"), (17, "Dwgs.User", "user", "User.Drawings"), (19, "Cmts.User", "user", "User.Comments"),
             (21, "Eco1.User", "user", "User.Eco1"), (23, "Eco2.User", "user", "User.Eco2"), (25, "Edge.Cuts", "user"), (27, "Margin", "user"),
             (31, "B.CrtYd", "user", "B.Courtyard"), (29, "F.CrtYd", "user", "F.Courtyard"), (35, "B.Fab", "user"), (33, "F.Fab", "user")]
REV = "A"
DATE = "2026-10-23"


def K(x, y):
    """maths frame -> KiCad frame (y down)"""
    return f(x), f(-y)


def footprint_sexp(part, netids, lib=LIB, standalone=False, board_pos=True):
    fp = part.fp
    L = part.layer
    layer_name = "F.Cu" if L == "F" else "B.Cu"
    silk = "F.SilkS" if L == "F" else "B.SilkS"
    fab = "F.Fab" if L == "F" else "B.Fab"
    crt = "F.CrtYd" if L == "F" else "B.CrtYd"
    s = []
    tag = "footprint"
    s.append(f'({tag} "{lib}:{fp.name}" (layer "{layer_name}") (uuid "{uid()}")')
    if board_pos:
        x, y = K(part.x, part.y)
        s.append(f' (at {x} {y} 0)')
    s.append(f' (descr "{fp.desc}") (tags "{fp.name}")')
    x0, y0, x1, y1 = fp.courtyard
    s.append(f' (property "Reference" "{part.ref}" (at {f(0)} {f(-(y1 + 1.0))} 0) (layer "{silk}") (uuid "{uid()}") (effects (font (size 0.8 0.8) (thickness 0.12))))')
    s.append(f' (property "Value" "{part.value}" (at 0 {f(-(y0 - 1.0))} 0) (layer "{fab}") (uuid "{uid()}") (effects (font (size 0.8 0.8) (thickness 0.12))))')
    s.append(f' (property "Footprint" "{lib}:{fp.name}" (at 0 0 0) (layer "{fab}") (hide yes) (uuid "{uid()}") (effects (font (size 1.27 1.27) (thickness 0.15))))')
    s.append(f' (property "Datasheet" "" (at 0 0 0) (layer "{fab}") (hide yes) (uuid "{uid()}") (effects (font (size 1.27 1.27) (thickness 0.15))))')
    s.append(f' (property "Description" "{fp.desc}" (at 0 0 0) (layer "{fab}") (hide yes) (uuid "{uid()}") (effects (font (size 1.27 1.27) (thickness 0.15))))')
    if part.mfr:
        s.append(f' (property "MPN" "{part.mfr}" (at 0 0 0) (layer "{fab}") (hide yes) (uuid "{uid()}") (effects (font (size 1.27 1.27) (thickness 0.15))))')
    smd = all(p.kind == "smd" for p in fp.pads if p.kind != "npth")
    s.append(f' (attr {"smd" if smd else "through_hole"}{" dnp" if part.dnp else ""})')
    for it in fp.silk:
        s.extend(_graphic(it, silk, 0.12, prefix="fp_"))
    for it in fp.fab:
        s.extend(_graphic(it, fab, 0.1, prefix="fp_"))
    a, b_ = K(x0, y0); c, d = K(x1, y1)
    s.append(f' (fp_rect (start {a} {b_}) (end {c} {d}) (stroke (width 0.05) (type default)) (fill no) (layer "{crt}") (uuid "{uid()}"))')
    for p in fp.pads:
        px, py = K(p.x, p.y)
        net = part.nets.get(p.name)
        netstr = f' (net {netids[net]} "{net}")' if net else ""
        if p.kind == "npth":
            s.append(f' (pad "" np_thru_hole circle (at {px} {py}) (size {f(p.drill)} {f(p.drill)}) (drill {f(p.drill)}) (layers "*.Cu" "*.Mask") (uuid "{uid()}"))')
            continue
        shape = {"roundrect": "roundrect", "rect": "rect", "circle": "circle", "oval": "oval"}[p.shape]
        rrs = f' (roundrect_rratio {p.rr})' if shape == "roundrect" else ""
        if p.kind == "tht":
            if isinstance(p.drill, tuple):
                dw, dl = (p.drill[0], p.drill[1]) if p.w < p.h else (p.drill[1], p.drill[0])
                drl = f"(drill oval {f(dw)} {f(dl)})"
            else:
                drl = f"(drill {f(p.drill)})"
            s.append(f' (pad "{p.name}" thru_hole {shape} (at {px} {py}) (size {f(p.w)} {f(p.h)}) {drl} (layers "*.Cu" "*.Mask"){rrs} (remove_unused_layers no){netstr} (uuid "{uid()}"))')
        else:
            lay = "F" if p.layer == "F" else "B"
            s.append(f' (pad "{p.name}" smd {shape} (at {px} {py}) (size {f(p.w)} {f(p.h)}) (layers "{lay}.Cu" "{lay}.Paste" "{lay}.Mask"){rrs}{netstr} (uuid "{uid()}"))')
    s.append(")")
    return "\n".join(s)


def _graphic(it, layer, width, prefix="gr_"):
    if it[0] == "line":
        a, b_ = K(it[1], it[2]); c, d = K(it[3], it[4])
        return [f' ({prefix}line (start {a} {b_}) (end {c} {d}) (stroke (width {width}) (type solid)) (layer "{layer}") (uuid "{uid()}"))']
    if it[0] == "circle":
        a, b_ = K(it[1], it[2])
        return [f' ({prefix}circle (center {a} {b_}) (end {f(it[1] + it[3])} {f(-it[2])}) (stroke (width {width}) (type solid)) (fill no) (layer "{layer}") (uuid "{uid()}"))']
    if it[0] == "rect":
        a, b_ = K(it[1], it[2]); c, d = K(it[3], it[4])
        return [f' ({prefix}rect (start {a} {b_}) (end {c} {d}) (stroke (width {width}) (type solid)) (fill no) (layer "{layer}") (uuid "{uid()}"))']
    return []


def write_kicad_pcb(board, path, title=""):
    nets = board.nets()
    netids = {n: i + 1 for i, n in enumerate(nets)}
    s = ['(kicad_pcb (version 20241229) (generator "pcbnew") (generator_version "9.0")',
         f' (general (thickness {f(board.thickness)}) (legacy_teardrops no))', ' (paper "A4")',
         f' (title_block (title "{title or board.name}") (date "{DATE}") (rev "{REV}"))']
    s.append(' (layers')
    for L in LAYERS_V9:
        if len(L) == 4:
            s.append(f'  ({L[0]} "{L[1]}" {L[2]} "{L[3]}")')
        else:
            s.append(f'  ({L[0]} "{L[1]}" {L[2]})')
    s.append(' )')
    s.append(' (setup (pad_to_mask_clearance 0) (allow_soldermask_bridges_in_footprints no)')
    s.append('  (pcbplotparams (layerselection 0x00000000_00000000_55555555_5755f5ff) (plot_on_all_layers_selection 0x00000000_00000000_00000000_00000000) (disableapertmacros no) (usegerberextensions yes) (usegerberattributes yes) (usegerberadvancedattributes yes) (creategerberjobfile yes) (dashed_line_dash_ratio 12.000000) (dashed_line_gap_ratio 3.000000) (svgprecision 4) (plotframeref no) (mode 1) (useauxorigin no) (hpglpennumber 1) (hpglpenspeed 20) (hpglpendiameter 15.000000) (pdf_front_fp_property_popups yes) (pdf_back_fp_property_popups yes) (pdf_metadata yes) (pdf_single_document no) (dxfpolygonmode yes) (dxfimperialunits yes) (dxfusepcbnewfont yes) (psnegative no) (psa4output no) (plot_black_and_white yes) (plotinvisibletext no) (sketchpadsonfab no) (plotpadnumbers no) (hidednponfab no) (sketchdnponfab yes) (crossoutdnponfab yes) (subtractmaskfromsilk no) (outputformat 1) (mirror no) (drillshape 1) (scaleselection 1) (outputdirectory "gerbers/"))')
    s.append(' )')
    s.append(' (net 0 "")')
    for n in nets:
        s.append(f' (net {netids[n]} "{n}")')
    for part in board.parts.values():
        s.append(footprint_sexp(part, netids))
    # outline: rounded rectangle as lines + arcs, or a custom polygon as a polyline
    w, d, r = board.w, board.d, board.r
    ec = 'Edge.Cuts'
    if getattr(board, "outline_custom", False):
        pts = list(board.outline.exterior.coords)
        for (p, q) in zip(pts[:-1], pts[1:]):
            a, b_ = K(*p); c, dd = K(*q)
            s.append(f' (gr_line (start {a} {b_}) (end {c} {dd}) (stroke (width 0.05) (type default)) (layer "{ec}") (uuid "{uid()}"))')
        for (xh, yh, dh) in getattr(board, "extra_npth", []):
            a, b_ = K(xh, yh)
            s.append(f' (footprint "{LIB}:MouseBite" (layer "F.Cu") (uuid "{uid()}") (at {a} {b_} 0) (attr through_hole exclude_from_bom exclude_from_pos_files) (pad "" np_thru_hole circle (at 0 0) (size {f(dh)} {f(dh)}) (drill {f(dh)}) (layers "*.Cu" "*.Mask") (uuid "{uid()}")))')
    def gl(x0, y0, x1, y1):
        a, b_ = K(x0, y0); c, dd = K(x1, y1)
        return f' (gr_line (start {a} {b_}) (end {c} {dd}) (stroke (width 0.05) (type default)) (layer "{ec}") (uuid "{uid()}"))'
    def ga(x0, y0, xm, ym, x1, y1):
        a, b_ = K(x0, y0); m1, m2 = K(xm, ym); c, dd = K(x1, y1)
        return f' (gr_arc (start {a} {b_}) (mid {m1} {m2}) (end {c} {dd}) (stroke (width 0.05) (type default)) (layer "{ec}") (uuid "{uid()}"))'
    k = r * (1 - 1 / math.sqrt(2))
    if not getattr(board, "outline_custom", False):
        s += [gl(r, 0, w - r, 0), gl(w, r, w, d - r), gl(w - r, d, r, d), gl(0, d - r, 0, r),
              ga(w - r, 0, w - k, k, w, r), ga(w, d - r, w - k, d - k, w - r, d), ga(r, d, k, d - k, 0, d - r), ga(0, r, k, k, r, 0)]
    for (lay, x0, y0, x1, y1, wd) in board.gr_lines:
        a, b_ = K(x0, y0); c, dd = K(x1, y1)
        s.append(f' (gr_line (start {a} {b_}) (end {c} {dd}) (stroke (width {wd}) (type default)) (layer "{lay}") (uuid "{uid()}"))')
    for (lay, x, y, text, size, rot) in board.texts:
        a, b_ = K(x, y)
        s.append(f' (gr_text "{text}" (at {a} {b_} {rot}) (layer "{lay}") (uuid "{uid()}") (effects (font (size {size} {size}) (thickness {f(size * 0.15)}))))')
    for (lay, pts, wd, net) in board.tracks:
        ln = "F.Cu" if lay == "F" else "B.Cu"
        for (p, q) in zip(pts[:-1], pts[1:]):
            a, b_ = K(*p); c, dd = K(*q)
            s.append(f' (segment (start {a} {b_}) (end {c} {dd}) (width {f(wd)}) (layer "{ln}") (net {netids[net]}) (uuid "{uid()}"))')
    for (x, y, net, sz, dr) in board.vias:
        a, b_ = K(x, y)
        s.append(f' (via (at {a} {b_}) (size {f(sz)}) (drill {f(dr)}) (layers "F.Cu" "B.Cu") (net {netids[net]}) (uuid "{uid()}"))')
    for ko in board.keepouts:
        pts = " ".join(f"(xy {K(x, y)[0]} {K(x, y)[1]})" for (x, y) in list(ko.exterior.coords)[:-1])
        s.append(f' (zone (net 0) (net_name "") (layers "F&B.Cu") (uuid "{uid()}") (hatch edge 0.5) (connect_pads (clearance 0)) (min_thickness 0.25) (filled_areas_thickness no) (keepout (tracks not_allowed) (vias not_allowed) (pads not_allowed) (copperpour not_allowed) (footprints allowed)) (fill (thermal_gap 0.5) (thermal_bridge_width 0.5)) (polygon (pts {pts})))')
    for z in board.zones:
        ln = "F.Cu" if z["layer"] == "F" else "B.Cu"
        pts = " ".join(f"(xy {K(x, y)[0]} {K(x, y)[1]})" for (x, y) in list(z["poly"].exterior.coords)[:-1])
        fills = []
        for fp_ in z.get("fills", []):
            fpts = " ".join(f"(xy {K(x, y)[0]} {K(x, y)[1]})" for (x, y) in list(fp_.exterior.coords)[:-1])
            fills.append(f'  (filled_polygon (layer "{ln}") (pts {fpts}))')
        s.append(f' (zone (net {netids[z["net"]]}) (net_name "{z["net"]}") (layer "{ln}") (uuid "{uid()}") (name "{z.get("name", z["net"])}") (hatch edge 0.5) (priority {z["priority"]}) (connect_pads {"yes" if z.get("solid") else ""} (clearance {z.get("clearance", 0.25)})) (min_thickness 0.25) (filled_areas_thickness no) (fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5)) (polygon (pts {pts}))\n' + "\n".join(fills) + ')')
    s.append(')')
    with open(path, "w") as fh:
        fh.write("\n".join(s))


def write_pretty(board, folder, lib=LIB):
    os.makedirs(folder, exist_ok=True)
    seen = set()
    for part in board.parts.values():
        fp = part.fp0
        if fp.name in seen:
            continue
        seen.add(fp.name)
        dummy = Part(fp.name, fp, 0, 0, 0, "", {}, part.layer)
        dummy.ref = "REF**"
        txt = footprint_sexp(dummy, {}, lib, board_pos=False)
        txt = txt.replace(f'(footprint "{lib}:', '(footprint "').replace('(layer "F.Cu") (uuid', '(version 20241229) (generator "pcbnew") (generator_version "9.0") (layer "F.Cu") (uuid', 1)
        with open(os.path.join(folder, fp.name + ".kicad_mod"), "w") as fh:
            fh.write(txt)


def write_project(board, folder, lib=LIB):
    os.makedirs(folder, exist_ok=True)
    pro = {"board": {"design_settings": {"defaults": {}, "rules": {"min_clearance": 0.15, "min_copper_edge_clearance": 0.3, "min_hole_clearance": 0.25, "min_track_width": 0.2, "min_via_annular_width": 0.15, "min_via_diameter": 0.5, "min_through_hole_diameter": 0.3}},
                     "layer_presets": [], "viewports": []},
           "boards": [], "cvpcb": {"equivalence_files": []}, "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
           "meta": {"filename": f"{board.name}.kicad_pro", "version": 3}, "net_settings": {"classes": [{"name": "Default", "clearance": 0.15, "track_width": 0.25, "via_diameter": 0.6, "via_drill": 0.3}], "meta": {"version": 4}},
           "pcbnew": {"last_paths": {"gencad": "", "idf": "", "netlist": "", "plot": "gerbers/", "pos_files": "", "specctra_dsn": "", "step": "", "svg": "", "vrml": ""}, "page_layout_descr_file": ""},
           "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []}, "sheets": [], "text_variables": {}}
    with open(os.path.join(folder, f"{board.name}.kicad_pro"), "w") as fh:
        json.dump(pro, fh, indent=2)
    with open(os.path.join(folder, "fp-lib-table"), "w") as fh:
        fh.write(f'(fp_lib_table\n  (version 7)\n  (lib (name "{lib}")(type "KiCad")(uri "${{KIPRJMOD}}/{lib}.pretty")(options "")(descr "project footprints"))\n)\n')
    with open(os.path.join(folder, "sym-lib-table"), "w") as fh:
        fh.write(f'(sym_lib_table\n  (version 7)\n)\n')


def write_schematic(board, path, pin_names, title=""):
    """Machine-generated schematic: one box symbol per part, every pin wired to a global label with its net.
    pin_names: {footprint name: {pad: pin label}}. Opens in KiCad 9; 'Update PCB from schematic' matches by
    reference. Not pretty, but complete (all pins passive)."""
    root = uid()
    L = [f'(kicad_sch (version 20231120) (generator "eeschema") (generator_version "8.0") (uuid "{root}") (paper "A2")',
         f' (title_block (title "{title or board.name}") (date "{DATE}") (rev "{REV}"))', ' (lib_symbols']
    libs = {}
    parts = list(board.parts.values())
    for p in parts:
        fp = p.fp0
        if fp.name in libs:
            continue
        pads = []
        seen = set()
        for pd in fp.pads:
            if pd.kind == "npth" or pd.name in seen:
                continue
            seen.add(pd.name); pads.append(pd.name)
        libs[fp.name] = pads
        n = len(pads)
        half = (n + 1) // 2
        hgt = max(half, 2) * 2.54 + 2.54
        L.append(f'  (symbol "{LIB}:{fp.name}" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)')
        L.append(f'   (property "Reference" "U" (at 0 {f(hgt / 2 + 1.27)} 0) (effects (font (size 1.27 1.27))))')
        L.append(f'   (property "Value" "{fp.name}" (at 0 {f(-hgt / 2 - 1.27)} 0) (effects (font (size 1.27 1.27))))')
        L.append(f'   (property "Footprint" "{LIB}:{fp.name}" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))')
        L.append(f'   (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))')
        L.append(f'   (symbol "{fp.name}_0_1" (rectangle (start -7.62 {f(hgt / 2)}) (end 7.62 {f(-hgt / 2)}) (stroke (width 0.254) (type default)) (fill (type background))))')
        L.append(f'   (symbol "{fp.name}_1_1"')
        names = pin_names.get(fp.name, {})
        for i, pn in enumerate(pads):
            side = -1 if i < half else 1
            row = i if i < half else i - half
            y = hgt / 2 - 2.54 - row * 2.54
            x = -7.62 - 2.54 if side < 0 else 7.62 + 2.54
            ang = 0 if side < 0 else 180
            L.append(f'    (pin passive line (at {f(x)} {f(y)} {ang}) (length 2.54) (name "{names.get(pn, pn)}" (effects (font (size 1.0 1.0)))) (number "{pn}" (effects (font (size 1.0 1.0)))))')
        L.append('   )')
        L.append('  )')
    L.append(' )')
    # place symbols on a grid
    x0, y0 = 25.4, 25.4
    cursor_x, cursor_y, row_h = x0, y0, 0
    for p in parts:
        fp = p.fp0
        pads = libs[fp.name]
        n = len(pads); half = (n + 1) // 2
        hgt = max(half, 2) * 2.54 + 2.54
        wdt = 15.24 + 2 * 2.54 + 2 * 12.7
        if cursor_x + wdt > 560:
            cursor_x = x0; cursor_y += row_h + 12.7; row_h = 0
        cx, cy = cursor_x + wdt / 2, cursor_y + hgt / 2 + 5
        row_h = max(row_h, hgt + 10)
        cursor_x += wdt
        L.append(f' (symbol (lib_id "{LIB}:{fp.name}") (at {f(cx)} {f(cy)} 0) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp {"yes" if p.dnp else "no"}) (uuid "{uid()}")')
        L.append(f'  (property "Reference" "{p.ref}" (at {f(cx)} {f(cy - hgt / 2 - 1.27)} 0) (effects (font (size 1.27 1.27))))')
        L.append(f'  (property "Value" "{p.value}" (at {f(cx)} {f(cy + hgt / 2 + 1.27)} 0) (effects (font (size 1.27 1.27))))')
        L.append(f'  (property "Footprint" "{LIB}:{fp.name}" (at {f(cx)} {f(cy)} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
        L.append(f'  (property "Datasheet" "" (at {f(cx)} {f(cy)} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
        for pn in pads:
            L.append(f'  (pin "{pn}" (uuid "{uid()}"))')
        L.append(f'  (instances (project "{board.name}" (path "/{root}" (reference "{p.ref}") (unit 1))))')
        L.append(' )')
        for i, pn in enumerate(pads):
            net = p.nets.get(pn)
            side = -1 if i < half else 1
            row = i if i < half else i - half
            py = cy - (hgt / 2 - 2.54 - row * 2.54)           # schematic y is down: symbol-local +y -> up
            px = cx + (-(7.62 + 2.54) if side < 0 else (7.62 + 2.54))
            if not net:
                L.append(f' (no_connect (at {f(px)} {f(py)}) (uuid "{uid()}"))')
                continue
            ex = px + (-5.08 if side < 0 else 5.08)
            L.append(f' (wire (pts (xy {f(px)} {f(py)}) (xy {f(ex)} {f(py)})) (stroke (width 0) (type default)) (uuid "{uid()}"))')
            ang = 180 if side < 0 else 0
            just = "right" if side < 0 else "left"
            L.append(f' (global_label "{net}" (shape input) (at {f(ex)} {f(py)} {ang}) (fields_autoplaced yes) (effects (font (size 1.0 1.0)) (justify {just})) (uuid "{uid()}") (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {f(ex)} {f(py)} 0) (effects (font (size 1.0 1.0)) (hide yes))))')
    L.append(' (sheet_instances (path "/" (page "1")))')
    L.append(')')
    with open(path, "w") as fh:
        fh.write("\n".join(L))


def write_bom(board, path):
    rows = {}
    for p in board.parts.values():
        key = (p.value, p.fp0.name, p.mfr, p.dnp)
        rows.setdefault(key, []).append(p.ref)
    with open(path, "w") as fh:
        fh.write("Qty,Refs,Value,Footprint,MPN,DNP\n")
        for (v, fpn, m, dnp), refs in sorted(rows.items(), key=lambda kv: kv[1][0]):
            fh.write(f'{len(refs)},"{" ".join(sorted(refs))}","{v}",{fpn},"{m}",{"yes" if dnp else ""}\n')


def write_pos(board, path):
    with open(path, "w") as fh:
        fh.write("Ref,Val,Package,PosX,PosY,Rot,Side\n")
        for p in board.parts.values():
            fh.write(f"{p.ref},{p.value},{p.fp0.name},{p.x:.3f},{p.y:.3f},{p.rot},{'top' if p.layer == 'F' else 'bottom'}\n")


# ---------------------------------------------------------------------------
# SVG render (maths frame -> svg y down)
# ---------------------------------------------------------------------------
def render_svg(board, path, layers=("B", "F"), scale=8, show_silk=True, show_courtyard=False, title=""):
    _bx0, _by0, w, d = board.outline.bounds
    pad = 4
    W, H = (w + 2 * pad) * scale, (d + 2 * pad) * scale

    def T(x, y):
        return (x + pad) * scale, (d - y + pad) * scale

    def poly_path(g):
        parts = []
        for gg in _geoms(g):
            rings = [gg.exterior] + list(gg.interiors)
            for r in rings:
                pts = [T(*c) for c in r.coords]
                parts.append("M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z")
        return " ".join(parts)
    col = {"F": "#c0392b", "B": "#2471a3"}
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" viewBox="0 0 {W:.0f} {H:.0f}">',
         f'<rect width="100%" height="100%" fill="#f4f1e8"/>',
         f'<path d="{poly_path(board.outline)}" fill="#1e3d2b" stroke="#000" stroke-width="2"/>']
    for lay in layers:
        op = 0.95 if lay == layers[-1] else 0.55
        geo = board.copper(lay, exclude_zones=True)
        zones = unary_union([g for z in board.zones if z["layer"] == lay for g in z.get("fills", [])] or [Polygon()])
        s.append(f'<path d="{poly_path(zones)}" fill="{col[lay]}" fill-opacity="{op * 0.3:.2f}" fill-rule="evenodd"/>')
        s.append(f'<path d="{poly_path(geo)}" fill="{col[lay]}" fill-opacity="{op}" fill-rule="evenodd"/>')
    # holes
    for ((x, y), dr, plated) in board.holes():
        X, Y = T(x, y)
        s.append(f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="{dr / 2 * scale:.1f}" fill="#f4f1e8" stroke="#333" stroke-width="1"/>')
    # keepouts
    for ko in board.keepouts:
        s.append(f'<path d="{poly_path(ko)}" fill="none" stroke="#e67e22" stroke-width="2" stroke-dasharray="6,4"/>')
    if show_silk:
        for p in board.parts.values():
            if p.layer != "F":
                continue
            for it in p.fp.silk:
                if it[0] == "line":
                    a, b_ = T(p.x + it[1], p.y + it[2]); c, dd = T(p.x + it[3], p.y + it[4])
                    s.append(f'<line x1="{a:.1f}" y1="{b_:.1f}" x2="{c:.1f}" y2="{dd:.1f}" stroke="#fff" stroke-width="1.5"/>')
                elif it[0] == "rect":
                    a, b_ = T(p.x + it[1], p.y + it[4]); c, dd = T(p.x + it[3], p.y + it[2])
                    s.append(f'<rect x="{a:.1f}" y="{b_:.1f}" width="{c - a:.1f}" height="{dd - b_:.1f}" fill="none" stroke="#fff" stroke-width="1.5"/>')
                elif it[0] == "circle":
                    a, b_ = T(p.x + it[1], p.y + it[2])
                    s.append(f'<circle cx="{a:.1f}" cy="{b_:.1f}" r="{it[3] * scale:.1f}" fill="none" stroke="#fff" stroke-width="1.5"/>')
            x0, y0, x1, y1 = p.fp.courtyard
            a, b_ = T(p.x, p.y + y1 + 0.3)
            s.append(f'<text x="{a:.1f}" y="{b_:.1f}" font-size="{1.1 * scale:.0f}" fill="#ffd166" text-anchor="middle" font-family="monospace">{p.ref}</text>')
            if show_courtyard:
                a, b_ = T(p.x + x0, p.y + y1); c, dd = T(p.x + x1, p.y + y0)
                s.append(f'<rect x="{a:.1f}" y="{b_:.1f}" width="{c - a:.1f}" height="{dd - b_:.1f}" fill="none" stroke="#999" stroke-width="0.8" stroke-dasharray="3,3"/>')
    for (lay, x, y, text, size, rot) in board.texts:
        a, b_ = T(x, y)
        s.append(f'<text x="{a:.1f}" y="{b_:.1f}" font-size="{size * scale:.0f}" fill="#fff" text-anchor="middle" font-family="sans-serif" transform="rotate({-rot} {a:.1f} {b_:.1f})">{text}</text>')
    if title:
        s.append(f'<text x="{W / 2:.0f}" y="{H - 6:.0f}" font-size="{1.6 * scale:.0f}" fill="#333" text-anchor="middle" font-family="sans-serif">{title}</text>')
    s.append('</svg>')
    with open(path, "w") as fh:
        fh.write("\n".join(s))


# ---------------------------------------------------------------------------
# Own Gerber (RS-274X) + Excellon writer: everything from the board model, no KiCad needed.
# Pads/zones go out as regions (G36/G37), tracks as draws with round apertures, vias as flashes.
# ---------------------------------------------------------------------------
def _gfmt(v):
    return f"{int(round(v * 1e6)):d}"


class GerberWriter:
    def __init__(self, path, function):
        self.lines = ["%TF.GenerationSoftware,pcbkit,1.0*%", f"%TF.FileFunction,{function}*%", "%FSLAX46Y46*%", "%MOMM*%",
                      "%LPD*%", "G01*", "G75*"]
        self.path = path
        self.apertures = {}

    def ap(self, kind, *dims):
        key = (kind, tuple(round(d, 4) for d in dims))
        if key not in self.apertures:
            n = 10 + len(self.apertures)
            self.apertures[key] = n
        return self.apertures[key]

    def region(self, poly):
        # Holes are written with clear polarity (%LPC), which erases EVERYTHING drawn before it at that spot.
        # Write outer shapes first (largest exterior first), so a ring (e.g. the chamber outline on the silk)
        # cannot erase text that lies inside it.
        for g in sorted(_geoms(poly), key=lambda gg: -Polygon(gg.exterior).area):
            rings = [g.exterior] + list(g.interiors)
            for k, r in enumerate(rings):
                self.lines.append("%LPD*%" if k == 0 else "%LPC*%")
                pts = list(r.coords)
                self.lines.append("G36*")
                self.lines.append(f"X{_gfmt(pts[0][0])}Y{_gfmt(pts[0][1])}D02*")
                for (x, y) in pts[1:]:
                    self.lines.append(f"X{_gfmt(x)}Y{_gfmt(y)}D01*")
                self.lines.append("G37*")
            if len(rings) > 1:
                self.lines.append("%LPD*%")

    def draw(self, pts, width):
        n = self.ap("C", width)
        self.lines.append(f"D{n}*")
        self.lines.append(f"X{_gfmt(pts[0][0])}Y{_gfmt(pts[0][1])}D02*")
        for (x, y) in pts[1:]:
            self.lines.append(f"X{_gfmt(x)}Y{_gfmt(y)}D01*")

    def flash_circle(self, x, y, d):
        n = self.ap("C", d)
        self.lines.append(f"D{n}*")
        self.lines.append(f"X{_gfmt(x)}Y{_gfmt(y)}D03*")

    def save(self):
        head = self.lines[:7]
        body = self.lines[7:]
        aps = [f"%ADD{n}{k[0]},{'X'.join(f'{d:.4f}' for d in k[1])}*%" for k, n in self.apertures.items()]
        with open(self.path, "w") as fh:
            fh.write("\n".join(head + aps + body + ["M02*"]) + "\n")


def text_polys(text, x, y, size, rot=0, anchor="middle"):
    """text -> list of shapely polygons (matplotlib TextPath, DejaVu Sans), height ~ size mm"""
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
    from matplotlib.transforms import Affine2D
    tp = TextPath((0, 0), text, size=size * 1.35, prop=FontProperties(family="DejaVu Sans"))
    bb = tp.get_extents()
    dx = -bb.width / 2 if anchor == "middle" else 0
    tr = Affine2D().translate(dx - bb.x0, -bb.y0 - bb.height / 2).rotate_deg(rot).translate(x, y)
    tp = tp.transformed(tr)
    polys = []
    for p in tp.to_polygons():
        if len(p) >= 3:
            polys.append(Polygon(p))
    # even-odd: holes in letters
    out = []
    polys.sort(key=lambda g: -g.area)
    used = [False] * len(polys)
    for i, g in enumerate(polys):
        if used[i]:
            continue
        holes = [h for j, h in enumerate(polys) if j != i and not used[j] and g.contains(h)]
        for h in holes:
            used[polys.index(h)] = True
        out.append(Polygon(g.exterior.coords, [h.exterior.coords for h in holes]))
    return out


def export_gerbers_own(board, out_dir, name, mask_expand=0.05, silk_width=0.15, silk_clear=0.15):
    os.makedirs(out_dir, exist_ok=True)
    files = {}
    # --- copper, mask, paste per layer
    for lay, ext_cu, ext_mask, ext_paste, fn in (("F", "GTL", "GTS", "GTP", "Top"), ("B", "GBL", "GBS", "GBP", "Bot")):
        cu = GerberWriter(os.path.join(out_dir, f"{name}.{ext_cu}"), f"Copper,L{1 if lay == 'F' else 2},{'Top' if lay == 'F' else 'Bot'}")
        mask = GerberWriter(os.path.join(out_dir, f"{name}.{ext_mask}"), f"Soldermask,{fn}")
        paste = GerberWriter(os.path.join(out_dir, f"{name}.{ext_paste}"), f"Paste,{fn}")
        for part in board.parts.values():
            for pad, pos, n in part.pads():
                if pad.kind == "npth":
                    continue
                on = pad.kind == "tht" or pad.layer == lay
                if not on:
                    continue
                pp = board.pad_poly(pad, pos)
                cu.region(pp)
                mask.region(pp.buffer(mask_expand, join_style=1))
                if pad.kind == "smd":
                    paste.region(pp.buffer(-0.02))
        for (l2, pts, w, n) in board.tracks:
            if l2 == lay:
                cu.draw(pts, w)
        for (x, y, n, s, dr) in board.vias:
            cu.flash_circle(x, y, s)             # tented: no mask opening
        for z in board.zones:
            if z["layer"] == lay:
                for g in z.get("fills", []):
                    cu.region(g)
        cu.save(); mask.save(); paste.save()
        files[ext_cu] = cu.path; files[ext_mask] = mask.path; files[ext_paste] = paste.path
    # --- silkscreen (top + bottom), kept off the pads
    for lay, ext, fn in (("F", "GTO", "Top"), ("B", "GBO", "Bot")):
        silk = GerberWriter(os.path.join(out_dir, f"{name}.{ext}"), f"Legend,{fn}")
        pads_here = unary_union([board.pad_poly(p, pos).buffer(silk_clear) for part in board.parts.values() for p, pos, n in part.pads()
                                 if p.kind != "smd" or p.layer == lay] or [Polygon()])
        geoms = []
        for part in board.parts.values():
            if part.layer != lay:
                continue
            for it in part.fp.silk:
                if it[0] == "line":
                    geoms.append(LineString([(part.x + it[1], part.y + it[2]), (part.x + it[3], part.y + it[4])]).buffer(silk_width / 2))
                elif it[0] == "rect":
                    geoms.append(sbox(part.x + it[1], part.y + it[2], part.x + it[3], part.y + it[4]).exterior.buffer(silk_width / 2))
                elif it[0] == "circle":
                    geoms.append(Point(part.x + it[1], part.y + it[2]).buffer(it[3]).exterior.buffer(silk_width / 2))
            x0, y0, x1, y1 = part.fp.courtyard
            if not part.ref.startswith("H"):
                geoms.extend(text_polys(part.ref, part.x, part.y + y1 + 0.7, 0.8))
        for (l2, x0, y0, x1, y1, w) in board.gr_lines:
            if l2 == ("F.SilkS" if lay == "F" else "B.SilkS"):
                geoms.append(LineString([(x0, y0), (x1, y1)]).buffer(w / 2))
        for (l2, x, y, text, size, rot) in board.texts:
            if l2 == ("F.SilkS" if lay == "F" else "B.SilkS"):
                geoms.extend(text_polys(text, x, y, size, rot))
        silkgeo = unary_union(geoms).difference(pads_here).intersection(board.outline.buffer(-0.3))
        silk.region(silkgeo)
        silk.save(); files[ext] = silk.path
    # --- outline
    for ext in ("GKO", "GM1"):
        edge = GerberWriter(os.path.join(out_dir, f"{name}.{ext}"), "Profile,NP")
        edge.draw(list(board.outline.exterior.coords), 0.1)
        edge.save(); files[ext] = edge.path
    # --- drills (Excellon, metric, with slots)
    for plated, ext in ((True, "PTH.drl"), (False, "NPTH.drl")):
        tools, hits, slots = {}, [], []
        for part in board.parts.values():
            for pad, pos, n in part.pads():
                if pad.kind not in ("tht", "npth") or (pad.kind == "tht") != plated:
                    continue
                if isinstance(pad.drill, tuple):
                    d, L = pad.drill
                    ang = 90 if pad.h > pad.w else 0
                    half = (L - d) / 2
                    if ang == 90:
                        slots.append((d, (pos[0], pos[1] - half), (pos[0], pos[1] + half)))
                    else:
                        slots.append((d, (pos[0] - half, pos[1]), (pos[0] + half, pos[1])))
                else:
                    hits.append((pad.drill, pos))
        if plated:
            for (x, y, n, s, dr) in board.vias:
                hits.append((dr, (x, y)))
        else:
            for (xh, yh, dh) in getattr(board, "extra_npth", []):
                hits.append((dh, (xh, yh)))
        for d, _ in hits:
            tools.setdefault(round(d, 3), None)
        for d, _, _ in slots:
            tools.setdefault(round(d, 3), None)
        for i, d in enumerate(sorted(tools)):
            tools[d] = i + 1
        L = ["M48", "METRIC,TZ", f";TYPE={'PLATED' if plated else 'NON_PLATED'}"]
        for d, t in sorted(tools.items(), key=lambda kv: kv[1]):
            L.append(f"T{t:02d}C{d:.3f}")
        L.append("G90"); L.append("G05"); L.append("%")
        for d, t in sorted(tools.items(), key=lambda kv: kv[1]):
            L.append(f"T{t:02d}")
            for dd, (x, y) in hits:
                if round(dd, 3) == d:
                    L.append(f"X{x:.3f}Y{y:.3f}")
            for dd, (x0, y0), (x1, y1) in slots:
                if round(dd, 3) == d:
                    L.append(f"X{x0:.3f}Y{y0:.3f}G85X{x1:.3f}Y{y1:.3f}")
        L.append("T0"); L.append("M30")
        p = os.path.join(out_dir, f"{name}-{ext}")
        with open(p, "w") as fh:
            fh.write("\n".join(L) + "\n")
        files[ext] = p
    with open(os.path.join(out_dir, "README.txt"), "w") as fh:
        fh.write(f"{name} - Gerber RS-274X (mm, 4.6) + Excellon (mm, slots as G85), rev {REV}, UNVERIFIED design\n"
                 "Generated by pcbkit, not plotted by KiCad. Re-plot from KiCad before ordering.\n"
                 "GTL/GBL copper, GTS/GBS solder mask (negative), GTP/GBP paste, GTO/GBO silkscreen, GKO (=GM1, same content) outline, *-PTH.drl / *-NPTH.drl drills.\n"
                 "2 layers, 1.6 mm FR4, 1 oz, HASL lead-free, min track/space 0.15 mm, min drill 0.3 mm, vias tented.\n")
    return files
