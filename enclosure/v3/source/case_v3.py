# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Daniel Bernet
"""
Voice satellite V3 enclosure (for the custom main board, rev A) - UNVERIFIED DESIGN, never printed
=================================================================================================
Code-CAD (build123d). Frame: X width (left->right from the front), Y depth (front face y=0),
Z up (z=0 = underside of the base plate). Reads the board geometry exported by the PCB script:

    python3 ../../../hardware/v3-pcb/source/satellite_v3_pcb.py    # writes hardware/v3-pcb/board_for_case.json
    python3 case_v3.py                                             # -> ../stl (print orientation), ../step, ../build

Concept (vs V2):
  * The PCB is the floor of everything: it carries the LED ring, so there is no plinth. It sits on
    4 standoffs of the base plate; 4x M3x16 from below go through base plate + PCB into bosses that
    hang from the shell ceiling -> base, PCB and shell are clamped by the same 4 hidden screws
    (TPU feet press over the heads).
  * Sealed speaker chamber: walls hang from the ceiling and stand on the PCB top face with a TPU
    rib gasket in a groove (the PCB has a part-free, via-free rim band there). The bosses are the
    hard stop. Speaker on top firing through the hex grille, mounted from inside (V2 mount).
  * Light ring: a clear PCTG band in the lower wall (z BAND_Z0..BAND_Z1), printed in the same object
    as the black shell (multi-material: import shell_black + shell_band_clear as ONE object with two
    parts in Bambu Studio). A 45 deg light lip above the band keeps the glow out of the bay.
  * USB-C receptacle (GCT USB4085, board-edge type) pokes through a cutout in the back wall; the
    cutout is open to the parting line and closed by a tongue on the base plate.
  * Mic module on a small carrier PCB (breakaway from the main board), screwed into two inserts on the
    front wall; the module sits in the V2 port ring with the TPU gasket. 90 deg to the speaker.
  * Speaker wires solder to two pads inside the sealed chamber: no connector, no grommet, no hole.
  * All screws go into heat-set inserts except the TPU feet pegs (V2 threaded straight into PETG).
"""
import math, json, os, sys, itertools
from build123d import *

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BRD = json.load(open(os.path.join(HERE, "..", "..", "..", "hardware", "v3-pcb", "board_for_case.json")))

# --------------------------------------------------------------------------- printing / fasteners (V2 values)
WALL, TOP_T, BASE_T = 2.4, 2.4, 3.0
R_VERT, R_TOP = 8.0, 3.0
TOP_EDGE = "chamfer"
BASE_CHAMFER = 0.6
SAC = 0.2
PILOT_D, PILOT_CSK = 2.6, 0.4
SCREW_CLEAR_D, SCREW_HEAD_D, SCREW_HEAD_CB = 3.4, 6.4, 2.0
HEAD_D, HEAD_H = 5.7, 1.65

# --------------------------------------------------------------------------- PCB
PCB_W, PCB_D, PCB_R, PCB_T = BRD["W"], BRD["D"], BRD["R"], BRD["thickness"]
GAP = 3.0                 # PCB edge -> inner wall (light channel), front / right
GAP_LEFT = 5.2            # left: the ESP32 antenna overhangs the PCB edge by 4.3 mm (plastic beside it is fine)
GAP_BACK = 0.4            # back: the USB-C receptacle front must reach the wall (2.5 mm overhang past the PCB edge)
STANDOFF_H, STANDOFF_D = 4.0, 6.5
OX, OY = WALL + GAP_LEFT, WALL + GAP                 # PCB origin in case coordinates
Z_PCB0 = BASE_T + STANDOFF_H
Z_PCB1 = Z_PCB0 + PCB_T
W = WALL + GAP_LEFT + PCB_W + GAP + WALL
D = WALL + GAP + PCB_D + GAP_BACK + WALL
H = 54.0
HOLES = [(OX + x, OY + y) for (x, y) in BRD["HOLES"]]
USB_X = OX + 39.0                                   # receptacle centre (J1 at PCB x 39)
USBC_W, USBC_H = 8.94, 3.26
USB_OVERHANG = 2.5                                  # receptacle front past the PCB edge (ESTIMATE from the footprint, verify on the GCT drawing)

# --------------------------------------------------------------------------- chamber (from the PCB CH lines)
cx0, cy0, cx1, cy1 = BRD["CH"]
CH_X0, CH_Y0, CH_X1, CH_Y1 = OX + cx0, OY + cy0, OX + cx1, OY + cy1    # wall centre lines
CH_WALL = 2.6
GROOVE_W, GROOVE_D = 1.6, 1.4
GK_BASE_W, GK_BASE_H, GK_RIB_W, GK_RIB_H = 1.3, 1.1, 0.8, 0.8        # 1.9 tall in a 1.4 groove -> 0.5 proud, squeezed to the hard stop
SPK_CEIL_T = 6.5
Z_CEIL = H - SPK_CEIL_T
Z_BAY_CEIL = H - TOP_T

# speaker (V2 measured values)
SPK, SPK_DEPTH, SPK_FLANGE_T, SPK_FRONT = 40.0, 22.0, 1.0, 0.5
SPK_BODY_D, SPK_BODY_RING, SPK_MAGNET_D, SPK_SURROUND_D = 40.0, 6.0, 30.0, 36.0
SPK_HOLE_PITCH, SPK_HOLE_D = 32.0, 3.2
SPK_STANDOFF, BOSS_D, SPK_PILOT_D, SPK_PILOT_L = 3.0, 6.2, 2.6, 8.3
GRILLE_R, GRILLE_HOLE, GRILLE_PITCH = 15.5, 2.0, 3.0
SG_RIB_R, SG_RIB_W, SG_RIB_H, SG_COMPRESSION = 18.75, 0.7, 0.9, 0.5
SPK_CX = (CH_X0 + CH_X1) / 2 + 0.8                 # 0.8 to the right: room for the terminal wires on the bay side
SPK_CY = (CH_Y0 + CH_Y1) / 2
Z_FL_FRONT = Z_CEIL - SPK_STANDOFF
Z_FL_BACK = Z_FL_FRONT - SPK_FLANGE_T
SPK_SCREWS = [(SPK_CX + sx * SPK_HOLE_PITCH / 2, SPK_CY + sy * SPK_HOLE_PITCH / 2) for sx in (-1, 1) for sy in (-1, 1)]

# light band + lip
BAND_Z0, BAND_Z1 = BASE_T + 2.5, BASE_T + 13.0
LIP_Z, LIP_IN = BAND_Z1 + 1.0, 5.0

# mic on the front wall (V2 ring)
MIC_D, MIC_T, MIC_ROW, MIC_NOTCH_W, MIC_ACROSS = 14.0, 1.6, 4.0, 2.0, 12.5
PORT_BOSS_D, PORT_BOSS_H = 5.4, 1.6
MIC_GK_OD, MIC_GK_ID, MIC_GK_T, MIC_GK_POCKET = 4.6, 2.2, 0.9, 0.6
MIC_PORT_D, MIC_PORT_CSK_D = 2.0, 3.6
MIC_SHOULDER_R0, MIC_RING_T = 6.0, 1.6
MIC_BORE_R = MIC_D / 2 + 0.2
MIC_X, MIC_Z = 30.0, 40.0
# mic carrier (breakaway PCB from the main board order): 27 x 24 x 1.6, module centre 3.5 above the carrier centre,
# JST-PH below the module, 2x M3 at +-10 mm. Stack from the wall: ring boss 1.6 | module 1.6 | header plastic 2.5 | carrier 1.6
CAR_W, CAR_H, CAR_T = 27.0, 24.0, 1.6
CAR_HOLE_DX = 10.0
HDR_PLASTIC = 2.5
Y_CARRIER0 = WALL + PORT_BOSS_H + MIC_T + HDR_PLASTIC      # carrier wall-side face
Y_CARRIER1 = Y_CARRIER0 + CAR_T
CAR_Z0 = MIC_Z - (CAR_H / 2 + 3.5)                          # carrier bottom edge
MIC_BOSS_D = 8.0
# heat-set inserts: M3x6x4.5 (hole 4.3), M3x5x4.2 / M3x4x4.2 (hole 4.0). Hole depth = screw reach + 0.5
INS_HOLE_45, INS_HOLE_42 = 4.3, 4.0
CORNER_INS_DEPTH = 7.5        # M3x16 through 3 + 4 + 1.6 = 8.6 -> 7.4 reach, insert M3x6x4.5
SPK_INS_DEPTH = 6.8           # M3x8 through flange 1 + gasket -> 6.3 reach, insert M3x5x4.2
MIC_INS_DEPTH = 6.5           # M3x8 through the 1.6 carrier -> 6.4 reach, insert M3x4x4.2
LIP_H, LIP_T, LIP_CLR = 2.3, 1.2, 0.2   # base-plate alignment lip inside the shell wall
Y_MIC_PORT = WALL + PORT_BOSS_H
Y_MIC_BACK = Y_MIC_PORT + MIC_T

# feet (V2 press-fit feet over the screw heads)
FOOT_D, FOOT_H, FOOT_PEG_D, FOOT_PEG_OFF, FOOT_PEG_L = 16.0, 3.0, 2.6, 4.7, 2.0
BOSS_CORNER_D = 7.0

C = {"case": "#3b4048", "base": "#2b2f35", "tpu": "#e8873a", "pctg": "#bfe6ff", "pcb": "#2f8a4c", "part": "#8d96a3",
     "module": "#b9bec6", "usb": "#d9dde2", "spk": "#1b1b1b", "spk_cone": "#555a61", "mic": "#101820", "ko": "#e0564a", "led": "#fff2a8", "header": "#1a1a1a"}


# --------------------------------------------------------------------------- helpers (V2)
def box(x0, x1, y0, y1, z0, z1):
    return Pos(x0, y0, z0) * Box(x1 - x0, y1 - y0, z1 - z0, align=(Align.MIN, Align.MIN, Align.MIN))


def cyl_z(x, y, z0, z1, d):
    return Pos(x, y, z0) * Cylinder(d / 2, z1 - z0, align=(Align.CENTER, Align.CENTER, Align.MIN))


def cyl_x(y, z, x0, x1, d):
    return Pos((x0 + x1) / 2, y, z) * Rot(0, 90, 0) * Cylinder(d / 2, abs(x1 - x0))


def cyl_y(x, z, y0, y1, d):
    return Pos(x, (y0 + y1) / 2, z) * Rot(90, 0, 0) * Cylinder(d / 2, abs(y1 - y0))


def pilot_z(x, y, z_mouth, depth, direction=+1, d=None):
    d = PILOT_D if d is None else d
    z0, z1 = (z_mouth - 0.1, z_mouth + depth) if direction > 0 else (z_mouth - depth, z_mouth + 0.1)
    hole = cyl_z(x, y, z0, z1, d)
    r0, r1 = d / 2 + PILOT_CSK, d / 2
    if direction > 0:
        cone = Pos(x, y, z_mouth - 0.01) * Cone(r0, r1, PILOT_CSK + 0.01, align=(Align.CENTER, Align.CENTER, Align.MIN))
    else:
        cone = Pos(x, y, z_mouth - PILOT_CSK) * Cone(r1, r0, PILOT_CSK + 0.01, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return hole + cone


def ring_z(x, y, z0, z1, r_in, r_out):
    return cyl_z(x, y, z0, z1, 2 * r_out) - cyl_z(x, y, z0 - 1, z1 + 1, 2 * r_in)


def ring_y(x, z, y0, y1, r_in, r_out):
    return cyl_y(x, z, y0, y1, 2 * r_out) - cyl_y(x, z, y0 - 1, y1 + 1, 2 * r_in)


def rr(x0, x1, y0, y1, z0, z1, r):
    r = min(max(r, 0.2), (x1 - x0) / 2 - 0.01, (y1 - y0) / 2 - 0.01)
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, z0) * extrude(RectangleRounded(x1 - x0, y1 - y0, r), amount=z1 - z0)


def rr_offset(outline, d, z0, z1):
    x0, x1, y0, y1, r = outline
    return rr(x0 - d, x1 + d, y0 - d, y1 + d, z0, z1, r + d)


def rr_band(outline, d_in, d_out, z0, z1):
    return rr_offset(outline, d_out, z0, z1) - rr_offset(outline, d_in, z0 - 1, z1 + 1)


def teardrop_y(x, z, y0, y1, d):
    r = d / 2
    wedge = Pos(x, (y0 + y1) / 2, z + r / math.sqrt(2)) * Rot(0, 45, 0) * Box(r, abs(y1 - y0), r)
    return cyl_y(x, z, y0, y1, d) + wedge


def union(shapes):
    out = None
    for s in shapes:
        out = s if out is None else out + s
    return out


def vol(a, b):
    try:
        i = a & b
        return i.volume if i is not None else 0.0
    except Exception:
        return float("nan")


CHAMBER_CL = (CH_X0, CH_X1, CH_Y0, CH_Y1, 3.0)     # wall centre-line outline (corner r 3)
OUTER = (0, W, 0, D, R_VERT)


# --------------------------------------------------------------------------- components + keep-outs
def components():
    parts = {}
    pcb = rr(OX, OX + PCB_W, OY, OY + PCB_D, Z_PCB0, Z_PCB1, PCB_R)
    for (x, y) in HOLES:
        pcb -= cyl_z(x, y, Z_PCB0 - 1, Z_PCB1 + 1, 3.2)
    parts["pcb"] = (pcb, C["pcb"])
    ko = []
    for p in BRD["parts"]:
        if p["ref"].startswith("H") or p["dnp"]:
            continue
        if p["ref"] in ("MIC1", "J6"):
            continue                                                          # carrier parts: modelled with the carrier below
        x0, y0, x1, y1 = p["bounds"]
        h = max(p["height"], 0.6)
        if p["fp"].startswith("LED") or p["ref"] == "U1":
            x0, y0, x1, y1 = x0 + 0.3, y0 + 0.3, x1 - 0.3, y1 - 0.3          # body (courtyard - 0.3 margin)
        b = box(OX + x0, OX + x1, OY + y0, OY + y1, Z_PCB1, Z_PCB1 + h)
        if p["ref"] == "U1":
            parts["esp32_module"] = (b, C["module"])
        elif p["ref"] == "J1":
            xc = (x0 + x1) / 2
            parts["usbc"] = (box(OX + xc - USBC_W / 2, OX + xc + USBC_W / 2, OY + PCB_D - 6.6, OY + PCB_D + USB_OVERHANG, Z_PCB1, Z_PCB1 + 3.46), C["usb"])
        elif p["fp"].startswith("LED"):
            parts.setdefault("leds", []).append(b)
        else:
            ko.append(b)
    parts["leds"] = (union(parts["leds"]), C["led"])
    parts["pcb_parts"] = (union(ko), C["part"])
    # USB-C plug: 12.4 x 6.5 overmold outside, metal plug through the wall
    y_face = D
    parts["usb_plug_keepout"] = (box(USB_X - 6.5, USB_X + 6.5, y_face + 0.3, y_face + 25, Z_PCB1 - 1.6, Z_PCB1 + 5.0), C["ko"])
    # solder joints under the PCB (THT leads 2 mm)
    parts["pcb_bottom_solder_keepout"] = (rr(OX + 2, OX + PCB_W - 2, OY + 2, OY + PCB_D - 2, Z_PCB0 - 2.0, Z_PCB0, PCB_R), C["ko"])

    # speaker (V2)
    flange = Pos(SPK_CX, SPK_CY, Z_FL_BACK) * extrude(RectangleRounded(SPK, SPK, 4), amount=SPK_FLANGE_T)
    for (sx, sy) in SPK_SCREWS:
        flange -= cyl_z(sx, sy, Z_FL_BACK - 1, Z_FL_FRONT + 1, SPK_HOLE_D)
    z_bottom = Z_FL_FRONT - SPK_DEPTH
    ring = cyl_z(SPK_CX, SPK_CY, Z_FL_BACK - SPK_BODY_RING, Z_FL_BACK + 0.01, SPK_BODY_D)
    magnet = cyl_z(SPK_CX, SPK_CY, z_bottom, Z_FL_BACK - SPK_BODY_RING + 0.01, SPK_MAGNET_D)
    parts["speaker"] = (flange + ring + magnet, C["spk"])
    parts["speaker_cone"] = (cyl_z(SPK_CX, SPK_CY, Z_FL_FRONT - 0.01, Z_FL_FRONT + SPK_FRONT, SPK_SURROUND_D), C["spk_cone"])
    parts["spk_cable_keepout"] = (box(CH_X0 + CH_WALL / 2 + 0.1, SPK_CX - SPK_BODY_D / 2, SPK_CY - 5, SPK_CY + 5, Z_FL_BACK - 12, Z_FL_BACK - 0.01), C["ko"])
    parts["spk_screw_heads"] = (union([cyl_z(sx, sy, Z_FL_BACK - HEAD_H, Z_FL_BACK, HEAD_D) for (sx, sy) in SPK_SCREWS]), C["ko"])
    parts["spk_key_paths"] = (union([cyl_z(sx, sy, Z_PCB1 + 0.5, Z_FL_BACK - HEAD_H - 0.01, 2.4) for (sx, sy) in SPK_SCREWS]), C["ko"])

    # mic (V2)
    b = cyl_y(MIC_X, MIC_Z, Y_MIC_PORT, Y_MIC_BACK, MIC_D)
    b += box(MIC_X - 1.8, MIC_X + 1.8, Y_MIC_BACK, Y_MIC_BACK + 1.0, MIC_Z - 1.4, MIC_Z + 1.4)
    parts["mic"] = (b, C["mic"])
    # header plastic + pins between module and carrier, carrier, JST on the carrier's bay side, solder below
    hdr = union([box(MIC_X + sx * 3.81 - 1.3, MIC_X + sx * 3.81 + 1.3, Y_MIC_BACK, Y_CARRIER0 + 0.01, MIC_Z - 3.9, MIC_Z + 3.9) for sx in (-1, 1)])
    parts["mic_header"] = (hdr, "#1a1a1a")
    car = box(MIC_X - CAR_W / 2, MIC_X + CAR_W / 2, Y_CARRIER0, Y_CARRIER1, CAR_Z0, CAR_Z0 + CAR_H)
    for sx in (-1, 1):
        car -= cyl_y(MIC_X + sx * CAR_HOLE_DX, MIC_Z, Y_CARRIER0 - 1, Y_CARRIER1 + 1, 3.2)
    parts["mic_carrier"] = (car, C["pcb"])
    parts["mic_jst_keepout"] = (box(MIC_X - 8, MIC_X + 8, Y_CARRIER1, Y_CARRIER1 + 7.0, CAR_Z0 + 1.0, CAR_Z0 + 7.5), C["ko"])
    parts["mic_solder_keepout"] = (box(MIC_X - 6, MIC_X + 6, Y_CARRIER1, Y_CARRIER1 + 2.5, MIC_Z - 4.5, MIC_Z + 4.5), C["ko"])
    parts["mic_screw_heads"] = (union([cyl_y(MIC_X + sx * CAR_HOLE_DX, MIC_Z, Y_CARRIER1, Y_CARRIER1 + HEAD_H, HEAD_D) for sx in (-1, 1)]), C["ko"])
    return parts


# --------------------------------------------------------------------------- shell (black) + band (clear)
def shell_full():
    outer = rr(0, W, 0, D, BASE_T, H, R_VERT)
    top = outer.edges().group_by(Axis.Z)[-1]
    outer = fillet(top, radius=R_TOP) if TOP_EDGE == "fillet" else chamfer(top, length=R_TOP)
    r_in = R_VERT - WALL
    cavity = rr(WALL, W - WALL, WALL, D - WALL, BASE_T - 1, Z_BAY_CEIL, r_in)
    s = outer - cavity
    # chamber: solid block hanging from the ceiling, hollowed; walls 2.6 thick centred on the CH lines
    blk = rr_offset(CHAMBER_CL, CH_WALL / 2, Z_PCB1, Z_BAY_CEIL + 0.1)
    s += blk & outer
    s -= rr_offset(CHAMBER_CL, -CH_WALL / 2, Z_PCB1 - 1, Z_CEIL)
    s -= rr_band(CHAMBER_CL, -GROOVE_W / 2, GROOVE_W / 2, Z_PCB1 - 1, Z_PCB1 + GROOVE_D)   # gasket groove in the rim
    # light lip: 45 deg wedge ring on the inner wall above the band
    lip = rr_band((WALL, W - WALL, WALL, D - WALL, r_in), -LIP_IN, 0.5, LIP_Z, LIP_Z + LIP_IN)
    # the slope: inner edge rises from LIP_Z (LIP_IN inboard) to LIP_Z + LIP_IN at the wall, in 10 steps
    slope = None
    steps = 10
    for i in range(steps):
        z0 = LIP_Z + i * LIP_IN / steps
        d_in = -LIP_IN + i * LIP_IN / steps + 0.001
        piece = rr_offset((WALL, W - WALL, WALL, D - WALL, r_in), d_in, z0, LIP_Z + LIP_IN + 0.01)
        slope = piece if slope is None else slope + piece
    lip -= slope
    s += lip & outer
    # corner bosses: from the PCB top to the ceiling, insert from the PCB face (M3x16 from below)
    for (x, y) in HOLES:
        s += cyl_z(x, y, Z_PCB1, Z_BAY_CEIL + 0.1, BOSS_CORNER_D) & outer
        s -= cyl_z(x, y, Z_PCB1 - 0.1, Z_PCB1 + CORNER_INS_DEPTH, INS_HOLE_45)        # M3x6x4.5 insert from the PCB face
    # speaker bosses + grille (V2)
    for (sx, sy) in SPK_SCREWS:
        s += cyl_z(sx, sy, Z_FL_FRONT, Z_CEIL + 0.1, BOSS_D + 0.8)
        s -= cyl_z(sx, sy, Z_FL_FRONT - 0.1, Z_FL_FRONT + SPK_INS_DEPTH, INS_HOLE_42)   # M3x5x4.2 insert, iron from inside the chamber
    n = int(GRILLE_R // GRILLE_PITCH) + 2
    holes = []
    for j in range(-n, n + 1):
        for i in range(-n, n + 1):
            hx = SPK_CX + (i + 0.5 * (j % 2)) * GRILLE_PITCH
            hy = SPK_CY + j * GRILLE_PITCH * math.sqrt(3) / 2
            if math.hypot(hx - SPK_CX, hy - SPK_CY) <= GRILLE_R - GRILLE_HOLE / 2:
                holes.append(cyl_z(hx, hy, Z_CEIL - 0.1, H + 1, GRILLE_HOLE))
    s -= union(holes)
    # USB-C cutout in the back wall, open to the parting line (shell lowers over the receptacle)
    s -= box(USB_X - USBC_W / 2 - 0.3, USB_X + USBC_W / 2 + 0.3, D - WALL - 1, D + 1, BASE_T - 1, Z_PCB1 + USBC_H + 0.3)
    # mic ring on the front wall (V2)
    y_w = WALL - 0.1
    s += teardrop_y(MIC_X, MIC_Z, y_w, Y_MIC_BACK, 2 * (MIC_BORE_R + MIC_RING_T))
    s -= cyl_y(MIC_X, MIC_Z, Y_MIC_PORT, Y_MIC_BACK + 1, 2 * MIC_BORE_R)
    s -= ring_y(MIC_X, MIC_Z, WALL, Y_MIC_PORT + 0.01, PORT_BOSS_D / 2, MIC_SHOULDER_R0)
    s -= cyl_y(MIC_X, MIC_Z, Y_MIC_PORT - MIC_GK_POCKET, Y_MIC_PORT + 0.01, MIC_GK_OD + 0.2)
    for sx in (-1, 1):                                            # carrier bosses with inserts (iron reaches coaxially from the bay)
        bx = MIC_X + sx * CAR_HOLE_DX
        s += teardrop_y(bx, MIC_Z, y_w, Y_CARRIER0, MIC_BOSS_D)
        s -= cyl_y(bx, MIC_Z, Y_CARRIER0 - MIC_INS_DEPTH, Y_CARRIER0 + 0.1, INS_HOLE_42)
    s -= cyl_y(MIC_X, MIC_Z, -1, Y_MIC_PORT, MIC_PORT_D)
    csk_h = (MIC_PORT_CSK_D - MIC_PORT_D) / 2
    s -= Pos(MIC_X, csk_h - 0.01, MIC_Z) * Rot(90, 0, 0) * Cone(MIC_PORT_D / 2, MIC_PORT_CSK_D / 2 + 0.01, csk_h + 0.02, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return s


def band_cutter():
    """the clear band = the outer wall between BAND_Z0 and BAND_Z1 (full wall thickness), minus the USB cutout region"""
    r_in = R_VERT - WALL
    band = rr(0, W, 0, D, BAND_Z0, BAND_Z1, R_VERT) - rr(WALL, W - WALL, WALL, D - WALL, BAND_Z0 - 1, BAND_Z1 + 1, r_in)
    band -= box(USB_X - USBC_W / 2 - 2.5, USB_X + USBC_W / 2 + 2.5, D - WALL - 1, D + 1, BAND_Z0 - 1, BAND_Z1 + 1)  # keep the USB frame black
    band -= cyl_y(MIC_X, MIC_Z, -1, WALL + 1, 20)   # (mic is above the band anyway)
    return band


def base_plate():
    b = rr(0, W, 0, D, 0, BASE_T, R_VERT)
    b = chamfer(b.edges().group_by(Axis.Z)[0], length=BASE_CHAMFER)
    for (x, y) in HOLES:
        b += cyl_z(x, y, BASE_T - 0.1, Z_PCB0, STANDOFF_D)
        b -= cyl_z(x, y, SCREW_HEAD_CB + SAC, Z_PCB0 + 1, SCREW_CLEAR_D)
        b -= cyl_z(x, y, -1, SCREW_HEAD_CB, SCREW_HEAD_D)
        for sx in (-1, 1):                                       # foot pegs (V2 feet)
            b -= cyl_z(x + sx * FOOT_PEG_OFF, y, -1, FOOT_PEG_L + 0.4, FOOT_PEG_D)
    # tongue closing the USB cutout below the receptacle
    b += box(USB_X - USBC_W / 2 - 0.0, USB_X + USBC_W / 2 + 0.0, D - WALL, D, BASE_T - 0.1, Z_PCB1 - 0.3)
    # alignment lip: a ring just inside the shell wall, so base and shell cannot shift (no step in the outer seam)
    r_in = R_VERT - WALL
    b += rr_band((WALL, W - WALL, WALL, D - WALL, r_in), -LIP_CLR - LIP_T, -LIP_CLR, BASE_T - 0.1, BASE_T + LIP_H)
    return b


def chamber_gasket():
    z0 = Z_PCB1 + GROOVE_D - GK_BASE_H              # base sits in the groove, rib points down onto the PCB
    g = rr_band(CHAMBER_CL, -GK_BASE_W / 2, GK_BASE_W / 2, z0, z0 + GK_BASE_H)
    rib = rr_band(CHAMBER_CL, -GK_RIB_W / 2, GK_RIB_W / 2, z0 - GK_RIB_H, z0 + 0.01)
    return g + rib


def speaker_gasket():
    z_body = Z_FL_FRONT + SG_RIB_H - SG_COMPRESSION
    body = Pos(SPK_CX, SPK_CY, z_body) * extrude(RectangleRounded(SPK, SPK, 4), amount=Z_CEIL - z_body)
    body -= cyl_z(SPK_CX, SPK_CY, z_body - 1, Z_CEIL + 1, 2 * SG_RIB_R - SG_RIB_W - 0.2)
    rib = ring_z(SPK_CX, SPK_CY, z_body - SG_RIB_H, z_body + 0.01, SG_RIB_R - SG_RIB_W / 2, SG_RIB_R + SG_RIB_W / 2)
    g = body + rib
    for (sx, sy) in SPK_SCREWS:
        g -= cyl_z(sx, sy, z_body - 2, Z_CEIL + 1, BOSS_D + 0.6)
    return g


def mic_gasket():
    return ring_y(MIC_X, MIC_Z, Y_MIC_PORT - MIC_GK_POCKET, Y_MIC_PORT - MIC_GK_POCKET + MIC_GK_T, MIC_GK_ID / 2, MIC_GK_OD / 2)


def feet():
    f = None
    for (fx, fy) in HOLES:
        foot = cyl_z(fx, fy, -FOOT_H, 0, FOOT_D)
        foot = fillet(foot.edges().group_by(Axis.Z)[0], radius=1.0)
        for sx in (-1, 1):
            foot += cyl_z(fx + sx * FOOT_PEG_OFF, fy, -0.01, FOOT_PEG_L, FOOT_PEG_D)
        f = foot if f is None else f + foot
    return f


def build():
    comps = components()
    full = shell_full()
    band = band_cutter() & full
    shell_black = full - band
    case = {
        "shell_black": (shell_black, C["case"]),
        "shell_band_clear": (band, C["pctg"]),
        "base_plate": (base_plate(), C["base"]),
        "chamber_gasket_TPU": (chamber_gasket(), C["tpu"]),
        "speaker_gasket_TPU": (speaker_gasket(), C["tpu"]),
        "mic_gasket_TPU": (mic_gasket(), C["tpu"]),
        "feet_TPU": (feet(), C["tpu"]),
    }
    return comps, case


PRINT = {
    "shell_black": ("flip", 1, "PCTG black - top face on the bed; import together with shell_band_clear as ONE object (2 parts)"),
    "shell_band_clear": ("flip", 1, "PCTG clear - second part of the shell object (same orientation)"),
    "base_plate": ("asis", 1, "PETG/PCTG black - flat"),
    "chamber_gasket_TPU": ("flip", 1, "TPU black - rib up"),
    "speaker_gasket_TPU": ("flip", 1, "TPU black - flat face down, rib up"),
    "mic_gasket_TPU": ("y_down", 1, "TPU black - tiny ring, print spares"),
    "feet_TPU": ("asis", 4, "TPU black - one foot, print 4 (V2 feet fit)"),
}


def print_pose(name, shape):
    mode = PRINT[name][0]
    if name == "feet_TPU":
        fx, fy = HOLES[0]
        shape = shape & box(fx - 10, fx + 10, fy - 10, fy + 10, -100, 100)
    if mode == "flip":
        shape = Rot(180, 0, 0) * shape
    elif mode == "x_down":
        shape = Rot(0, 90, 0) * shape
    elif mode == "y_down":
        shape = Rot(-90, 0, 0) * shape
    bb = shape.bounding_box()
    if name.startswith("shell"):            # shells are posed together in __main__
        return shape
    return Pos(-(bb.min.X + bb.max.X) / 2, -(bb.min.Y + bb.max.Y) / 2, -bb.min.Z) * shape


if __name__ == "__main__":
    comps, case = build()
    build_dir, stl_dir, step_dir = (os.path.join(ROOT, d) for d in ("build", "stl", "step"))
    for d in (build_dir, stl_dir, step_dir):
        os.makedirs(d, exist_ok=True)
    children = []
    for name, (shape, col) in {**comps, **case}.items():
        shape.label = name
        shape.color = Color(col)
        children.append(shape)
        export_stl(shape, os.path.join(build_dir, f"{name}.stl"), tolerance=0.05, angular_tolerance=0.2)
    # print poses: the two shell parts share one frame (flipped, translated so z>=0 and centred)
    sh = case["shell_black"][0]; bd = case["shell_band_clear"][0]
    flipped = {n: Rot(180, 0, 0) * s for n, s in (("shell_black", sh), ("shell_band_clear", bd))}
    bb = flipped["shell_black"].bounding_box()
    T = Pos(-(bb.min.X + bb.max.X) / 2, -(bb.min.Y + bb.max.Y) / 2, -bb.min.Z)
    for n, s in flipped.items():
        export_stl(T * s, os.path.join(stl_dir, f"{n}.stl"), tolerance=0.02, angular_tolerance=0.15)
    for name, (shape, _) in case.items():
        if name.startswith("shell"):
            continue
        export_stl(print_pose(name, shape), os.path.join(stl_dir, f"{name}.stl"), tolerance=0.02, angular_tolerance=0.15)
    export_step(Compound(label="voice_satellite_V3", children=children), os.path.join(step_dir, "voice_satellite_v3_assembly.step"))
    info = {"W": round(W, 2), "D": round(D, 2), "H": H, "PCB_origin": (OX, OY), "Z_PCB1": Z_PCB1, "chamber_cl": CHAMBER_CL,
            "chamber_inner": (CH_X0 + CH_WALL / 2, CH_X1 - CH_WALL / 2, CH_Y0 + CH_WALL / 2, CH_Y1 - CH_WALL / 2, Z_PCB1, Z_CEIL),
            "spk_c": (round(SPK_CX, 2), round(SPK_CY, 2)), "Z_CEIL": Z_CEIL, "holes": HOLES, "usb_x": USB_X, "band_z": (BAND_Z0, BAND_Z1)}
    print(json.dumps(info))
