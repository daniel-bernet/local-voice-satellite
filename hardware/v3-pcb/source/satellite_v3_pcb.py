# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Daniel Bernet
"""
Voice satellite V3 - main board, rev A (PCB-as-code, see pcbkit.py)
====================================================================
UNVERIFIED DESIGN: generated and checked in code only, never fabricated or tested.

100 x 72 mm main board + 27 x 24 mm mic-carrier breakaway (100 x 98 mm panel), 2 layers, 1.6 mm FR4.
Frame: X right, Y up, origin = front-left corner of the main board. Front edge (y=0) = microphone side,
back edge (y=72) = USB-C side; the ESP32 antenna points over the LEFT edge. The speaker chamber of the
case stands on the right part of the board (CH rectangle): no parts and no vias there, the chamber wall
gasket presses on the solder mask inside the band around the CH lines.

Hand-solderable with an iron: the only exposed-pad parts (U1 module EPAD, U4 amp EP) get back-solder
holes. Pin map vs the hand-wired V2: mic SCK/WS/SD = IO11/IO12/IO13, amp BCLK/LRC/DIN = IO47/IO48/IO21,
amp SD = IO7 and LED data = IO14 unchanged, USB-C CC sense on IO4/IO5 (new).

Run:  python3 satellite_v3_pcb.py      (writes ../kicad, ../gerbers, ../renders, ../bom.csv, ...)
"""
import os, sys, math, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pcbkit import *
from pcbkit import _geoms
from shapely.geometry import box as sbox, Point, Polygon, LineString
from shapely.ops import unary_union

# --------------------------------------------------------------------------- parameters
W, D, R = 100.0, 72.0, 6.0
CH = (47.0, 8.3, 92.7, 63.7)       # chamber wall centre lines on the PCB (2.6 mm wide rim with gasket groove: keep +-1.6 mm clear)
HOLES = [(4.5, 4.5), (95.5, 4.5), (95.5, 67.5), (4.5, 44.5)]   # 4th screw mid-left: the top-left corner is the antenna
MOD_X, MOD_Y = 8.45, 60.5          # ESP32 module centre, rotated 90: antenna points over the LEFT board edge (4.3 mm beyond)
LED_FRONT = [12, 24, 36, 48, 60, 72, 84]      # y = 4
LED_BACK = [50, 62, 74, 86]                   # y = 68
LED_RIGHT = [54, 40, 26, 12]                  # x = 97.3
LED_LEFT = [12, 24, 36]                       # x = 4
RING = [(46.0, 70.0), (86.5, 70.0), (98.0, 58.5), (98.0, 13.5), (86.5, 2.0), (13.5, 2.0), (2.0, 13.5), (2.0, 49.0)]   # +5V bus, bottom

b = Board("voice_sat_v3", W, D, R)
# mic carrier breakaway (27 x 24) behind the back edge, joined by two 3 mm mouse-bite tabs -> same fab order
CAR = (60.0, 74.0, 87.0, 98.0)
_carrier = sbox(*CAR).buffer(-2).buffer(2, join_style=1, resolution=12)
_tabs = unary_union([sbox(tx - 1.5, D - 0.5, tx + 1.5, CAR[1] + 0.5) for tx in (66.0, 81.0)])
b.outline = unary_union([b.outline, _carrier, _tabs])
b.outline_custom = True
b.extra_npth = [(tx + k * 0.75, CAR[1], 0.5) for tx in (66.0, 81.0) for k in (-1.5, -0.5, 0.5, 1.5)]   # mouse bites on the carrier edge

# --------------------------------------------------------------------------- parts
FP = {"chip": fp_chip("0805"), "ptc": fp_chip("1812"), "sma": fp_sma(), "sot223": fp_sot223(), "sot23_5": fp_sot23(5),
      "sot23_6": fp_sot23(6), "tqfn": fp_tqfn16_3x3(), "radial": fp_radial(8.0, 3.5), "ph2": fp_jst_ph(2), "ph6": fp_jst_ph(6),
      "tact": fp_tact_6x6(), "led": fp_ws2812b(), "sj": fp_solder_jumper3(),
      "hole": fp_mounting_hole(3.2, 3.8), "esp": fp_esp32s3_wroom1(), "usbc": fp_usb4085(), "wire": fp_wire_pad(), "mic": fp_mic_module_2x3(7.62)}
FP["usbc"].may_overhang = True
FP["esp"].may_overhang = True
FP["hole"].may_overhang = True

P = lambda *a, **k: b.add(Part(*a, **k))

# ESP32-S3-WROOM-1-N16R8 (module pin numbers; 4/5 = IO4/IO5, 19/20/21 = IO11/IO12/IO13, 22 = IO14, 23/24/25 = IO21/IO47/IO48)
esp_nets = {"1": "GND", "2": "+3V3", "3": "EN", "7": "AMP_SD", "4": "CC1_S", "5": "CC2_S", "13": "USB_DM", "14": "USB_DP",
            "19": "MIC_SCK", "20": "MIC_WS", "21": "MIC_SD", "22": "LED_DATA", "23": "AMP_DIN", "24": "AMP_BCLK", "25": "AMP_LRC",
            "27": "IO0", "40": "GND", "41": "GND"}   # bottom row carries mic/amp/LED so the left corridor stays free
P("U1", FP["esp"], MOD_X, MOD_Y, 90, "ESP32-S3-WROOM-1-N16R8", esp_nets, mfr="ESP32-S3-WROOM-1-N16R8")

# USB-C (GCT USB4085-GF-A, 16 pin THT), board edge at local y = 6.1
usb_nets = {"A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS",
            "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DM", "B7": "USB_DM", "S1": "GND"}
P("J1", FP["usbc"], 39.0, 72.0 - 6.1, 0, "USB-C 2.0 receptacle THT", usb_nets, mfr="GCT USB4085-GF-A")

# USB power path / protection / CC
P("F1", FP["ptc"], 42.5, 61.3, 270, "PTC 3A 1812", {"1": "VBUS", "2": "+5V"}, mfr="Bel 0ZCJ0300FF2E (any 1812 3 A PTC)")
P("D1", FP["sma"], 44.1, 52.5, 90, "SMAJ5.0A TVS", {"1": "+5V", "2": "GND"}, mfr="SMAJ5.0A")
P("U2", FP["sot23_6"], 37.0, 59.5, 180, "USBLC6-2SC6", {"1": "USB_DM", "2": "GND", "3": "USB_DP", "4": "USB_DP", "5": "+5V", "6": "USB_DM"}, mfr="USBLC6-2SC6")
P("R1", FP["chip"], 34.2, 62.8, 90, "5.1k", {"1": "CC1", "2": "GND"})
P("R3", FP["chip"], 34.2, 58.4, 270, "10k", {"1": "CC1", "2": "CC1_S"})
P("R2", FP["chip"], 31.7, 62.8, 90, "5.1k", {"1": "CC2", "2": "GND"})
P("R4", FP["chip"], 31.7, 58.4, 270, "10k", {"1": "CC2", "2": "CC2_S"})

# 3.3 V LDO
P("U3", FP["sot223"], 39.0, 48.6, 0, "TLV1117LV33 (AMS1117-3.3 fits)", {"1": "GND", "2": "+3V3", "3": "+5V"}, mfr="TLV1117LV33DCYR")
P("C1", FP["chip"], 37.0, 42.4, 0, "10u", {"1": "+5V", "2": "GND"})
P("C2", FP["chip"], 32.1, 41.4, 90, "10u", {"1": "+3V3", "2": "GND"})
# module supply + EN
P("C3", FP["chip"], 10.0, 48.8, 0, "10u", {"1": "+3V3", "2": "GND"})
P("R5", FP["chip"], 14.5, 49.1, 0, "10k", {"1": "+3V3", "2": "EN"})
P("C4", FP["chip"], 8.5, 40.5, 90, "100n", {"1": "+3V3", "2": "GND"})
P("C5", FP["chip"], 13.0, 45.3, 0, "1u", {"1": "EN", "2": "GND"})
P("SW1", FP["tact"], 11.2, 30.0, 0, "RESET", {"1": "EN", "2": "GND"})
P("SW2", FP["tact"], 20.0, 30.0, 0, "BOOT", {"1": "IO0", "2": "GND"})

# microphone connector (ICS-43434 / INMP441 module on the carrier, JST-PH pigtail)
P("J2", FP["ph6"], 25.0, 10.0, 0, "MIC (3V3 GND LR WS SCK SD)", {"1": "+3V3", "2": "GND", "3": "GND", "4": "MIC_WS", "5": "MIC_SCK", "6": "MIC_SD"}, mfr="JST B6B-PH-K-S")

# amplifier (bare chip)
amp_nets = {"1": "AMP_DIN", "2": "GAIN", "3": "GND", "4": "AMP_SD", "7": "+5V", "8": "+5V", "9": "SPK_P", "10": "SPK_N", "11": "GND",
            "14": "AMP_LRC", "15": "GND", "16": "AMP_BCLK", "17": "GND"}
P("U4", FP["tqfn"], 36.0, 31.0, 0, "MAX98357A", amp_nets, mfr="MAX98357AETE+T")
P("C6", FP["chip"], 42.0, 30.0, 90, "10u", {"1": "+5V", "2": "GND"})
P("C7", FP["chip"], 36.0, 24.3, 0, "100n", {"1": "+5V", "2": "GND"})
P("JP1", FP["sj"], 41.5, 35.0, 0, "GAIN (GND=12dB open=9dB 5V=3dB)", {"1": "GND", "2": "GAIN", "3": "+5V"})
P("R7", FP["chip"], 32.5, 38.4, 0, "10k", {"1": "AMP_SD", "2": "GND"})
# speaker: two solder pads INSIDE the sealed chamber (no connector, no grommet, no hole)
P("W1", FP["wire"], 52.0, 16.0, 0, "SPK+", {"1": "SPK_P"})
P("W2", FP["wire"], 52.0, 21.5, 0, "SPK-", {"1": "SPK_N"})
# mic carrier (breakaway): module pads, JST-PH 6 to the main board's J2 (1:1 pigtail), 2x M3 for inserts in the wall bosses
mic_nets = {"1": "M_GND", "2": "M_WS", "3": "M_SCK", "4": "M_GND", "5": "M_3V3", "6": "M_SD"}   # A: L/R WS SCK (top->bottom)  B: GND VDD SD
P("MIC1", FP["mic"], 73.5, 89.0, 0, "INMP441 / ICS-43434 module", mic_nets)
P("J6", FP["ph6"], 73.5, 78.0, 0, "to J2 (3V3 GND LR WS SCK SD)", {"1": "M_3V3", "2": "M_GND", "3": "M_GND", "4": "M_WS", "5": "M_SCK", "6": "M_SD"}, mfr="JST B6B-PH-K-S")
P("H5", FP["hole"], 63.5, 89.0, 0, "M3 carrier", {})
P("H6", FP["hole"], 83.5, 89.0, 0, "M3 carrier", {})
P("C8", FP["radial"], 12.3, 16.0, 0, "470u/10V", {"1": "+5V", "2": "GND"})
P("C10", FP["radial"], 23.0, 42.0, 0, "470u/10V", {"1": "+5V", "2": "GND"})

# LED data path
P("U5", FP["sot23_5"], 33.4, 54.2, 270, "74AHCT1G125", {"1": "GND", "2": "LED_DATA", "3": "GND", "4": "LED_Y", "5": "+5V"}, mfr="SN74AHCT1G125DBVR")
P("C9", FP["chip"], 40.6, 55.8, 90, "100n", {"1": "+5V", "2": "GND"})
P("R9", FP["chip"], 31.0, 50.0, 270, "10k", {"1": "LED_DATA", "2": "GND"})
P("R8", FP["chip"], 37.5, 54.15, 0, "330", {"1": "LED_Y", "2": "LED_0"})

# LED ring: 18 x WS2812B, chain clockwise starting at the back row. Decoupling caps sit between the
# LEDs along the edge (keeps the inboard corridors free), the last one of each side goes inboard.
leds = []
for x in LED_BACK:
    leds.append((x, D - 4.0, 180))
for y in LED_RIGHT:
    leds.append((W - 3.0, y, 90))
for x in reversed(LED_FRONT):
    leds.append((x, 4.0, 0))
for y in LED_LEFT:
    leds.append((4.0, y, 270))
for i, (x, y, rot) in enumerate(leds):
    nin = f"LED_{i}"
    nout = f"LED_{i + 1}" if i < len(leds) - 1 else None
    nets = {"1": "+5V", "3": "GND", "4": nin}
    if nout:
        nets["2"] = nout
    P(f"D{i + 2}", FP["led"], x, y, rot, "WS2812B", nets, mfr="WS2812B-V5")
for i, (x, y, rot) in enumerate(leds):
    nxt = leds[i + 1] if i + 1 < len(leds) else None
    if nxt and nxt[2] == rot:
        cx, cy = (x + nxt[0]) / 2, (y + nxt[1]) / 2
    else:
        dx, dy = {0: (0, 4.0), 180: (0, -4.0), 90: (-4.0, 0), 270: (4.0, 0)}[rot]
        cx, cy = x + dx, y + dy
        if rot in (180, 90):
            continue                            # back-row / right-column end LEDs: the mid-row cap 6-7 mm away serves them (chamber rim is inboard)
    P(f"C{20 + i}", FP["chip"], cx, cy, 0 if rot in (0, 180) else 90, "100n", {"1": "+5V", "2": "GND"})

for i, (x, y) in enumerate(HOLES):
    P(f"H{i + 1}", FP["hole"], x, y, 0, "M3", {})

# --------------------------------------------------------------------------- keep-outs, silk
b.keepouts = [sbox(0, 50.5, MOD_X - 6.6, 72)]       # under/beside the antenna (module x <= 1.85): no copper on either layer
x0, y0, x1, y1 = CH
for (a, bb, c, d) in [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]:
    b.gr_lines.append(("F.SilkS", a, bb, c, d, 0.15))
b.texts += [("F.SilkS", 70, 38, "SPEAKER CHAMBER", 1.5, 0), ("F.SilkS", 70, 35, "keep clear - gasket rim on the line", 1.0, 0),
            ("F.SilkS", 70, 31, "VOICE SAT V3", 1.5, 0), ("B.SilkS", 70, 36, "VOICE SAT V3 - 2026-10", 1.5, 0),
            ("F.SilkS", 25.0, 14.5, "MIC: 3V3 GND LR WS SCK SD", 0.9, 0), ("F.SilkS", 56.5, 16.0, "SPK +", 0.9, 0), ("F.SilkS", 56.5, 21.5, "SPK -", 0.9, 0), ("F.SilkS", 73.5, 96.3, "MIC CARRIER - break off, screw to the front wall", 0.8, 0), ("F.SilkS", 66.0, 85.0, "L/R", 0.7, 90), ("F.SilkS", 81.0, 85.0, "GND", 0.7, 90), ("F.SilkS", 66.0, 93.0, "SCK", 0.7, 90), ("F.SilkS", 81.0, 93.0, "SD", 0.7, 90), ("F.SilkS", 73.5, 74.9, "port side -> wall", 0.7, 0),
            ("F.SilkS", 44.0, 63.0, "USB-C", 0.9, 90), ("F.SilkS", 11.2, 25.5, "RST", 0.9, 0), ("F.SilkS", 20.0, 25.5, "BOOT", 0.9, 0),
            ("F.SilkS", 12.0, 44.0, "ESP32-S3-WROOM-1 N16R8 - antenna left", 0.8, 0)]

# --------------------------------------------------------------------------- pre-placed copper
b.tracks.append(("B", RING, 1.2, "+5V"))
# USB pin field (0.85 mm pitch): pre-routed by hand, the grid router only takes over at the exit points
J1 = b.parts["J1"]
pp = {p.name: pos for p, pos, n in J1.pads()}
b.tracks.append(("F", [pp["A6"], pp["B6"]], 0.25, "USB_DP"))     # D+ pair link (top)
b.tracks.append(("B", [pp["A7"], pp["B7"]], 0.25, "USB_DM"))     # D- pair link (bottom)
for a, bb in (("A4", "B9"), ("A9", "B4")):                      # VBUS pairs (bottom)
    b.tracks.append(("B", [pp[a], pp[bb]], 0.3, "VBUS"))
for n in ("A4", "A9"):                                          # VBUS stubs (bottom) + join
    x, y = pp[n]
    b.tracks.append(("B", [(x, y), (x, 62.2)], 0.3, "VBUS"))
b.tracks.append(("B", [(pp["A4"][0], 62.2), (pp["A9"][0], 62.2)], 0.5, "VBUS"))
# signal stubs (top): straight down, then fan out to a wider pitch
Y_EXIT = 63.8
FAN_Y = 62.6
EXIT = {"VBUS": (pp["A9"][0], 62.2)}
for n, net, fx in (("A5", "CC1", pp["A5"][0] - 1.3), ("A6", "USB_DP", pp["A6"][0]), ("A7", "USB_DM", pp["A7"][0] + 1.3)):
    x, y = pp[n]
    b.tracks.append(("F", [(x, y), (x, Y_EXIT), (fx, FAN_Y)], 0.3, net))
    EXIT[net] = (fx, FAN_Y)
# CC2 leaves over the B row and comes down left of the USB, between the module and the CC resistors
b.tracks.append(("F", [pp["B5"], (pp["B5"][0], 68.7), (31.7, 68.7), (31.7, 66.3)], 0.3, "CC2"))
EXIT["CC2"] = (31.7, 66.3)

# pads that are internally connected inside a part still need copper between them
for ref, a, bb, wd in (("U2", "1", "6", 0.25), ("U2", "3", "4", 0.25), ("SW1", "1a", "1b", 0.4), ("SW1", "2a", "2b", 0.4), ("SW2", "1a", "1b", 0.4), ("SW2", "2a", "2b", 0.4), ("U3", "2a", "2b", 0.6)):
    part = b.parts[ref]
    pads = [(p, pos, n) for p, pos, n in part.pads()]
    if a.endswith("a"):
        same = [pos for p, pos, n in pads if p.name == a[0]]
        b.tracks.append(("F", [same[0], same[1]], wd, part.nets[a[0]]))
    else:
        pa = [pos for p, pos, n in pads if p.name == a][0]; pb = [pos for p, pos, n in pads if p.name == bb][0]
        b.tracks.append(("F", [pa, pb], wd, part.nets[a]))

# GND vias at the module (pins 1/40 lie beside the antenna keep-out)
P1 = (MOD_X - 5.26, MOD_Y - 8.75); P40 = (MOD_X - 5.26, MOD_Y + 8.75)      # module GND pins after the 90 deg rotation
b.vias += [(P1[0] + 0.4, P1[1] + 2.4, "GND", 0.6, 0.3), (P40[0], P40[1] - 1.6, "GND", 0.6, 0.3)]
b.tracks.append(("F", [P1, (P1[0] + 0.4, P1[1] + 2.4)], 0.4, "GND"))
b.tracks.append(("F", [P40, (P40[0], P40[1] - 1.6)], 0.4, "GND"))

# LED VDD: short top stub to a via beside the VDD pad (on the DOUT side, local (-4.3, 1.6)); the router
# joins the via to the +5V ring on the bottom layer (under the outboard pads, which are top-only)
ringline = LineString(RING)
LED_VIA = {}
for i, (x, y, rot) in enumerate(leds):
    part = b.parts[f"D{i + 2}"]
    vdd = [pos for p, pos, n in part.pads() if p.name == "1"][0]
    r = math.radians(rot)
    lx, ly = -4.3, 1.6
    vx, vy = x + lx * math.cos(r) - ly * math.sin(r), y + lx * math.sin(r) + ly * math.cos(r)
    b.vias.append((vx, vy, "+5V", 0.6, 0.3))
    b.tracks.append(("F", [vdd, (vx, vy)], 0.5, "+5V"))
    q = ringline.interpolate(ringline.project(Point(vx, vy)))
    LED_VIA[i] = ((vx, vy), (q.x, q.y))


# fan-out stubs for the 0.5 mm pitch amp pads: 0.45 mm straight, then spread to a 1.1 mm pitch line
def fanout(ref, side_pads, direction, pitch_out=1.1, dist=2.6, width=0.2):
    part = b.parts[ref]
    pos = {p.name: ps for p, ps, n in part.pads()}
    n = len(side_pads)
    dx, dy = direction
    px, py = -dy, dx
    cx = sum(pos[p][0] for p in side_pads) / n
    cy = sum(pos[p][1] for p in side_pads) / n
    ends = {}
    for i, p in enumerate(side_pads):
        net = part.nets.get(p)
        if not net:
            continue
        x, y = pos[p]
        s1 = (x + dx * 0.45, y + dy * 0.45)
        k = (i - (n - 1) / 2) * pitch_out
        e = (cx + dx * dist + px * k, cy + dy * dist + py * k)
        b.tracks.append(("F", [(x, y), s1, e], width, net))
        ends[p] = e
    return ends


FAN = {}
FAN.update(fanout("U4", ["1", "2", "3", "4"], (-1, 0)))
FAN.update(fanout("U4", ["5", "6", "7", "8"], (0, -1)))
FAN.update(fanout("U4", ["9", "10", "11", "12"], (1, 0)))
FAN.update(fanout("U4", ["13", "14", "15", "16"], (0, 1)))
b.tracks.append(("F", [FAN["7"], FAN["8"]], 0.3, "+5V"))        # VDD pins 7+8 joined at the fan line
for p, (dx, dy) in (("3", (-1, 0)), ("11", (1, 0)), ("15", (0, 1))):   # amp GND pins: stub 1.2 mm further out, then a via
    e = (FAN[p][0] + 1.2 * dx, FAN[p][1] + 1.2 * dy)
    b.tracks.append(("F", [FAN[p], e], 0.2, "GND"))
    b.vias.append((e[0], e[1], "GND", 0.6, 0.3))
b.tracks.append(("F", [(32.1, 53.25), (31.1, 52.9)], 0.3, "GND"))   # U5 GND pin 3 -> via
b.tracks.append(("F", [(32.1, 55.15), (31.2, 55.15), (31.2, 53.25), (32.1, 53.25)], 0.25, "GND"))   # U5 pin 1 (OE#) -> pin 3 GND loop
b.vias.append((31.1, 52.9, "GND", 0.6, 0.3))

# --------------------------------------------------------------------------- routing
rt = Router(b, grid=0.25, clearance=0.2, via_size=0.6, via_drill=0.3, edge_clear=0.6)
rt.seed_from_board(keepout_vias=[sbox(x0 - 1.6, y0 - 1.6, x1 + 1.6, y1 + 1.6).difference(sbox(x0 + 1.6, y0 + 1.6, x1 - 1.6, y1 - 1.6))])


def padpos(ref, pad):
    if ref == "U4" and str(pad) in FAN:
        return (FAN[str(pad)][0], FAN[str(pad)][1], "F")
    part = b.parts[ref]
    for p, pos, n in part.pads():
        if p.name == str(pad):
            return (pos[0], pos[1], "F" if p.kind == "smd" else "*")
    raise KeyError((ref, pad))


FAILS = []


def route(net, pins, width=0.25, **kw):
    pts = [padpos(*p) for p in pins]
    ok = rt.route_net(net, pts, width, **kw)
    if not ok:
        FAILS.append(rt.log[-1]); print("ROUTE FAIL", rt.log[-1])
    return ok


def route_pt(net, a, ref_pad, width, **kw):
    q = padpos(*ref_pad)
    ok = rt.route(net, a, q[:2], width, goal_layers=((q[2],) if q[2] in ("F", "B") else None), **kw)
    if not ok:
        FAILS.append(rt.log[-1]); print("ROUTE FAIL", rt.log[-1])
    return ok


# 1. LED supply vias -> bottom ring
for i in LED_VIA:
    (vx, vy), (qx, qy) = LED_VIA[i]
    if not rt.route("+5V", (vx, vy), (qx, qy), 0.5, layer_pref="B", allow_layers=("B",)):
        FAILS.append(rt.log[-1]); print("ROUTE FAIL LED via", i, rt.log[-1])
# 2. local power escapes that would otherwise get boxed in by signal tracks
route("+5V", [("U2", 5), ("F1", 2)], 0.4)
route("+5V", [("U5", 5), ("C9", 1)], 0.4)
route("+5V", [("U4", 7), ("C7", 1)], 0.4)
route("+5V", [("U4", 8), ("C6", 1)], 0.4)
route("+5V", [("C6", 1), ("JP1", 3)], 0.4)
# 3. constrained escapes: USB signals, CC, module signals, amp fan-outs
route_pt("USB_DP", EXIT["USB_DP"], ("U2", 3), 0.25)
route_pt("USB_DM", EXIT["USB_DM"], ("U2", 1), 0.25)
route("USB_DP", [("U2", 4), ("U1", 14)], 0.25)
route("USB_DM", [("U2", 6), ("U1", 13)], 0.25)
route_pt("CC1", EXIT["CC1"], ("R1", 1), 0.25)
route("CC1", [("R1", 1), ("R3", 1)], 0.25)
route_pt("CC2", EXIT["CC2"], ("R2", 1), 0.25)
route("CC2", [("R2", 1), ("R4", 1)], 0.25)
# bottom row of the module, right to left, so no escape gets sealed by an earlier track
route("AMP_LRC", [("U1", 25), ("U4", 14)], 0.25)
route("AMP_BCLK", [("U1", 24), ("U4", 16)], 0.25)
route("AMP_DIN", [("U1", 23), ("U4", 1)], 0.25)
route("IO0", [("U1", 27), ("SW2", 1)], 0.25)
route("LED_DATA", [("U5", 2), ("R9", 1), ("U1", 22)], 0.25)
route("MIC_SD", [("U1", 21), ("J2", 6)], 0.25)
route("MIC_WS", [("U1", 20), ("J2", 4)], 0.25)
route("MIC_SCK", [("U1", 19), ("J2", 5)], 0.25)
# left column
route("AMP_SD", [("U1", 7), ("R7", 1), ("U4", 4)], 0.25)
route("EN", [("U1", 3), ("R5", 2), ("C5", 1), ("SW1", 1)], 0.25)
route("CC1_S", [("R3", 2), ("U1", 4)], 0.25, via_cost=6.0)
route("CC2_S", [("R4", 2), ("U1", 5)], 0.25, via_cost=6.0)
route("GAIN", [("U4", 2), ("JP1", 2)], 0.25)
route("SPK_P", [("U4", 9), ("W1", 1)], 0.5)
route("SPK_N", [("U4", 10), ("W2", 1)], 0.5)
# mic carrier (local nets)
route("M_3V3", [("MIC1", 5), ("J6", 1)], 0.3)
route("M_GND", [("MIC1", 4), ("J6", 2), ("MIC1", 1), ("J6", 3)], 0.3)
route("M_WS", [("MIC1", 2), ("J6", 4)], 0.25)
route("M_SCK", [("MIC1", 3), ("J6", 5)], 0.25)
route("M_SD", [("MIC1", 6), ("J6", 6)], 0.25)
route("LED_Y", [("U5", 4), ("R8", 1)], 0.25)
route("LED_0", [("R8", 2), ("D2", 4)], 0.25)
for i in range(len(leds) - 1):
    route(f"LED_{i + 1}", [(f"D{i + 2}", 2), (f"D{i + 3}", 4)], 0.25, layer_pref="F")
# 4. power distribution
route("+3V3", [("U3", 2), ("C2", 1)], 0.5)
route("+3V3", [("C2", 1), ("C4", 1)], 0.5)
route("+3V3", [("C4", 1), ("U1", 2)], 0.5)
route("+3V3", [("U1", 2), ("C3", 1)], 0.5)
route("+3V3", [("C3", 1), ("R5", 1)], 0.4)
route("+3V3", [("C4", 1), ("J2", 1)], 0.5)
route_pt("VBUS", EXIT["VBUS"], ("F1", 1), 0.6, layer_pref="B")
route("+5V", [("F1", 2), ("D1", 1)], 0.8)
route("+5V", [("U3", 3), ("C1", 1)], 0.5)
route("+5V", [("D1", 1), ("C1", 1)], 0.8)
route("+5V", [("C1", 1), ("C9", 1)], 0.5)
route("+5V", [("C1", 1), ("C10", 1)], 0.8)
route_pt("+5V", (2.0, 16.0), ("C8", 1), 0.8, layer_pref="B")
route("+5V", [("C1", 1), ("C6", 1)], 0.8)
route_pt("+5V", RING[0], ("F1", 2), 0.8, layer_pref="B")
route_pt("+5V", RING[-1], ("C10", 1), 0.8, layer_pref="B")
for i in range(len(leds)):
    if f"C{20 + i}" in b.parts:
        route("+5V", [(f"C{20 + i}", 1), (f"D{i + 2}", 1)], 0.4, layer_pref="F")
print(f"routing: {len(FAILS)} failures")

# --------------------------------------------------------------------------- GND zones + stitching
full = sbox(0, 0, W, D).buffer(-R).buffer(R, join_style=1, resolution=16).buffer(-0.5)
b.zones.append({"layer": "B", "net": "GND", "poly": full, "priority": 0, "name": "GND_B"})
b.zones.append({"layer": "F", "net": "GND", "poly": full, "priority": 0, "name": "GND_F"})


def gnd_pads_in(poly):
    out = []
    for part in b.parts.values():
        for pad, pos, n in part.pads():
            if n == "GND" and poly.intersects(b.pad_poly(pad, pos)):
                out.append((pad, pos, part.ref))
    return out


def regroup(z):
    z["fills"] = [g for g in _geoms(unary_union(z["fills"]))]


def stitch():
    """every GND island (either layer) that holds pads but no via / THT pad gets a via to the other plane;
    islands without pads are dropped"""
    zf = [z for z in b.zones if z["layer"] == "F"][0]
    zb = [z for z in b.zones if z["layer"] == "B"][0]
    added = 0
    for z, other in ((zf, zb), (zb, zf)):
        otherfill = unary_union(other["fills"])
        keep = []
        vias_pts = [Point(x, y) for (x, y, n, s, dr) in b.vias if n == "GND"]
        for isl in z["fills"]:
            pads = gnd_pads_in(isl)
            if not pads:
                continue
            keep.append(isl)
            if any(isl.intersects(v.buffer(0.3)) for v in vias_pts) or any(p.kind == "tht" for p, pos, r in pads):
                continue
            cand = isl.buffer(-0.33).intersection(otherfill.buffer(-0.33))
            if cand.is_empty:
                print("  stitch: no via spot for island with", sorted({r for _, _, r in pads})); continue
            pt = cand.representative_point()
            b.vias.append((pt.x, pt.y, "GND", 0.6, 0.3)); vias_pts.append(pt); added += 1
        z["fills"] = keep
    return added


b.fill_zones(clearance=0.25)
for z in b.zones:
    regroup(z)
print("stitching vias added", stitch())
zb = [z for z in b.zones if z["layer"] == "B"][0]; zf = [z for z in b.zones if z["layer"] == "F"][0]
bot = unary_union(zb["fills"]); top = unary_union(zf["fills"])
grid_added = 0
for gx in range(6, int(W), 10):
    for gy in range(6, int(D), 10):
        p = Point(gx, gy)
        if bot.buffer(-0.6).contains(p) and top.buffer(-0.6).contains(p) and all(math.hypot(gx - x, gy - y) > 3 for (x, y, n, s, dr) in b.vias):
            b.vias.append((gx, gy, "GND", 0.6, 0.3)); grid_added += 1
print("grid stitching vias", grid_added)
b.fill_zones(clearance=0.25)
for z in b.zones:
    regroup(z)


# keep only GND copper that belongs to the main plane; report GND pads that end up on an orphan piece
def gnd_components():
    pieces = []
    for z in b.zones:
        for g in z["fills"]:
            pieces.append((z["layer"], g, z))
    for (lay, pts, w, n) in b.tracks:
        if n == "GND":
            pieces.append((lay, LineString(pts).buffer(w / 2), None))
    for part in b.parts.values():
        for pad, pos, n in part.pads():
            if n == "GND":
                pp = b.pad_poly(pad, pos)
                if pad.kind == "tht":
                    pieces.append(("F", pp, None)); pieces.append(("B", pp, None)); pieces.append(("X", pp, None))
                else:
                    pieces.append((pad.layer, pp, None))
    for (x, y, n, sz, dr) in b.vias:
        if n == "GND":
            pieces.append(("X", Point(x, y).buffer(sz / 2), None))
    parent = list(range(len(pieces)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for i in range(len(pieces)):
        for j in range(i + 1, len(pieces)):
            li, gi, _ = pieces[i]; lj, gj, _ = pieces[j]
            if (li == lj or "X" in (li, lj)) and gi.intersects(gj):
                parent[find(i)] = find(j)
    comps = {}
    for i in range(len(pieces)):
        comps.setdefault(find(i), []).append(i)
    main = max(comps.values(), key=lambda idx: sum(pieces[i][1].area for i in idx))
    return pieces, comps, set(main)


for _round in range(6):                                   # stitch orphan components to the main plane
    pieces, comps, main = gnd_components()
    added = 0
    main_fill = {L: unary_union([g for i, (l, g, zz) in enumerate(pieces) if zz is not None and l == L and i in main] or [Polygon()]) for L in ("F", "B")}
    for root, idx in comps.items():
        if set(idx) <= main:
            continue
        if not any(pieces[i][2] is None and pieces[i][0] != "X" for i in idx):
            continue                                           # no pad/track in it -> plain copper island, dropped below
        placed = False
        for i in idx:
            lay, g, zz = pieces[i]
            if lay == "X":
                continue
            other = "B" if lay == "F" else "F"
            cand = g.buffer(-0.33).intersection(main_fill[other].buffer(-0.33))
            if not cand.is_empty and all(math.hypot(cand.representative_point().x - x, cand.representative_point().y - y) > 0.8 for (x, y, n, sz, dr) in b.vias):
                pt = cand.representative_point()
                b.vias.append((pt.x, pt.y, "GND", 0.6, 0.3)); added += 1; placed = True
                break
        if not placed:
            # last resort: route a GND track from the orphan's pad/track to the nearest main-plane via
            src = None
            for i in idx:
                lay, g, zz = pieces[i]
                if zz is None and lay in ("F", "B"):
                    src = (g.representative_point().x, g.representative_point().y, lay); break
            mains = [(x, y) for i in main for (l, g, zz) in [pieces[i]] if l == "X" for (x, y) in [(g.centroid.x, g.centroid.y)]]
            if src and mains:
                mains.sort(key=lambda p: (p[0] - src[0]) ** 2 + (p[1] - src[1]) ** 2)
                for tgt in mains[:4]:
                    if rt.route("GND", (src[0], src[1]), tgt, 0.3, layer_pref=src[2], via_cost=4.0):
                        added += 1; break
    print(f"component stitching round {_round}: {added} vias/tracks, {len(comps)} components")
    if added == 0:
        break
    b.fill_zones(clearance=0.25)
    for z in b.zones:
        regroup(z)
pieces, comps, main = gnd_components()
orphan_pads = []
for z in b.zones:
    keep = []
    for g in z["fills"]:
        idx = [i for i, (l, gg, zz) in enumerate(pieces) if zz is z and gg is g][0]
        if idx in main:
            keep.append(g)
    z["fills"] = keep
for i, (lay, g, zz) in enumerate(pieces):
    if zz is None and i not in main and lay != "X":
        orphan_pads.append((lay, tuple(round(v, 1) for v in g.bounds)))
print("GND components:", len(comps), "orphan GND copper pieces (pads/tracks):", orphan_pads[:10])
for z in b.zones:
    out = []
    for g in z["fills"]:
        out.extend(fracture(g))
    z["fills"] = out

# --------------------------------------------------------------------------- checks + outputs
errs = [e for e in drc(b, clearance=0.15, edge_clear=0.3) if not (e.startswith("net GND:") and not orphan_pads)]
warn = [e for e in drc(b, clearance=0.2, edge_clear=0.3) if e.startswith("clearance")]
print(f"DRC: {len(errs)} issues, clearance warnings in 0.15..0.2 mm: {len(warn)}")
for e in errs[:80]:
    print("  ", e)
ROOT = os.path.dirname(HERE)
proj = os.path.join(ROOT, "kicad")
os.makedirs(proj, exist_ok=True)
write_kicad_pcb(b, os.path.join(proj, f"{b.name}.kicad_pcb"), "Voice satellite V3 main board (rev A, unverified)")
pin_names = {"ESP32-S3-WROOM-1": {"1": "GND", "2": "3V3", "3": "EN", "4": "IO4", "5": "IO5", "6": "IO6", "7": "IO7", "8": "IO15", "9": "IO16", "10": "IO17",
                                  "11": "IO18", "12": "IO8", "13": "IO19/D-", "14": "IO20/D+", "15": "IO3", "16": "IO46", "17": "IO9", "18": "IO10", "19": "IO11",
                                  "20": "IO12", "21": "IO13", "22": "IO14", "23": "IO21", "24": "IO47", "25": "IO48", "26": "IO45", "27": "IO0", "28": "IO35",
                                  "29": "IO36", "30": "IO37", "31": "IO38", "32": "IO39", "33": "IO40", "34": "IO41", "35": "IO42", "36": "RXD0", "37": "TXD0",
                                  "38": "IO2", "39": "IO1", "40": "GND", "41": "EPAD"},
             "TQFN-16_3x3": {"1": "DIN", "2": "GAIN_SLOT", "3": "GND", "4": "SD_MODE", "7": "VDD", "8": "VDD", "9": "OUTP", "10": "OUTN", "11": "GND", "14": "LRCLK", "15": "GND", "16": "BCLK", "17": "EP"},
             "SOT-223": {"1": "GND", "2": "VOUT", "3": "VIN"}, "SOT-23-5": {"1": "OE#", "2": "A", "3": "GND", "4": "Y", "5": "VCC"},
             "SOT-23-6": {"1": "IO1", "2": "GND", "3": "IO2", "4": "IO2", "5": "VBUS", "6": "IO1"},
             "LED_WS2812B_5050": {"1": "VDD", "2": "DOUT", "3": "GND", "4": "DIN"}, "D_SMA": {"1": "K", "2": "A"}, "CP_Radial_D8.0": {"1": "+", "2": "-"}}
write_schematic(b, os.path.join(proj, f"{b.name}.kicad_sch"), pin_names, "Voice satellite V3 (rev A, unverified)")
write_project(b, proj)
write_pretty(b, os.path.join(proj, f"{LIB}.pretty"))
write_bom(b, os.path.join(ROOT, "bom.csv"))
write_pos(b, os.path.join(ROOT, "positions.csv"))
json.dump({"W": W, "D": D, "R": R, "CH": CH, "HOLES": HOLES, "thickness": 1.6,
           "parts": [{"ref": p.ref, "bounds": list(p.courtyard().bounds), "height": p.fp0.height, "dnp": p.dnp, "fp": p.fp0.name} for p in b.parts.values()]},
          open(os.path.join(ROOT, "board_for_case.json"), "w"), indent=1)
export_gerbers_own(b, os.path.join(ROOT, "gerbers"), b.name)
os.makedirs(os.path.join(ROOT, "renders"), exist_ok=True)
render_svg(b, os.path.join(ROOT, "renders", "pcb_top.svg"), layers=("B", "F"), title="Voice sat V3 rev A (unverified) - top (red) over bottom (blue)")
render_svg(b, os.path.join(ROOT, "renders", "pcb_bottom.svg"), layers=("F", "B"), title="Voice sat V3 rev A (unverified) - bottom (blue) over top (red), seen from the top")
gnd_islands = b.connectivity_report()["GND"][0]
with open(os.path.join(ROOT, "drc_report.txt"), "w") as fh:
    fh.write(f"pcbkit geometric DRC on the board model (NOT KiCad's DRC)\n"
             f"rules: clearance 0.15, edge 0.3, hole-hole 0.25, annular 0.15, courtyards, connectivity\n"
             f"note: the GND island count is waived when no GND pad/track sits outside the main plane.\n"
             f"      GND copper islands in the generated fill: {gnd_islands} (orphaned GND pads/tracks: {len(orphan_pads)});\n"
             f"      any extra islands are pad-less fill pieces (dead copper). KiCad recomputes fills on 'Fill all zones'.\n"
             f"issues: {len(errs)}\n" + "\n".join(errs) + f"\n\nclearance warnings between 0.15 and 0.2 mm: {len(warn)}\n" + "\n".join(warn) +
             f"\n\nrouting failures: {len(FAILS)}\n" + "\n".join(FAILS) + "\n")
stats = {"tracks": len(b.tracks), "vias": len(b.vias), "parts": len(b.parts), "nets": len(b.nets()), "drc_issues": len(errs), "warnings": len(warn), "route_failures": len(FAILS), "orphan_gnd_pieces": len(orphan_pads)}
print(json.dumps(stats))
