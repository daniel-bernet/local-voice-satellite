# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Daniel Bernet
"""
Voice satellite V2 enclosure (hand-wired perfboard build) - printed, assembled and in use
=========================================================================================
Code-CAD model (build123d / OpenCascade). Everything is driven by the parameters below;
re-run the script to regenerate STEP/STL:

    python3 case_v2.py        # -> ../stl (print orientation), ../step, ../build (assembled parts, for checks/renders)

Coordinate system (case, assembled):
  X = width, left -> right as seen from the front
  Y = depth, front face at Y=0 -> back
  Z = up; Z=0 is the underside of the base plate (the plinth and feet sit below it)

Perfboard-local coordinates (from the top-view photos):
  u = along the 60 mm edge, u=0 at the USB edge, u=60 at the antenna edge
  w = along the 40 mm edge, w=0 at the ESP32 side, w=40 at the DAC side

Values marked (EST) were estimated from photos; MEASURED values were measured on the real parts.

V2 changes vs V1.2 (after test print 2)
  * Speaker moved to the TOP, firing up through a hex grille in the top face. It is screwed in from inside
    (4x M3x8 into bosses hanging from a 6.5 mm thick chamber ceiling). With the shell upside down and the
    base plate off, all four screws are reached straight down beside the round body (no visible screws).
  * Mic moved to the FRONT face (90 deg to the speaker, far from it). The board sits in a ring on the inside
    of the front wall; two pins pass the board's two edge notches and are heat-staked (like the perfboard).
    (In use these heat-staked pins broke under the wire forces - see docs/lessons-learned.md.)
  * Plinth (clear PCTG light band with the LED strip inside) kept from V1.2 unchanged. The case is sized around
    the content with the least overhang (3.75 mm at the sides, 5 mm front/back). Case -> plinth -> feet.
  * All 5 base-plate screws sit inside the plinth outline, so the plinth hides them (none in the overhang).
  * Bay 1.5 mm wider on the amp side: the amp's screw terminal faces the divider and the speaker wires need
    room to bend. Grommet channels sized for 1.5 mm wire. Mic tabs removed.
All screws are M3 button heads threaded straight into printed pilot holes (no heat-set inserts).
"""
import math
import os
from build123d import *

HERE = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------
# Parameters: general / printing
# --------------------------------------------------------------------------
WALL = 2.4          # side / front / back wall (6 perimeters @ 0.4 mm)
TOP_T = 2.4         # top wall over the electronics bay
BASE_T = 5.0        # base plate
R_VERT = 8.0        # vertical outer edge radius
R_TOP = 3.0         # top outer edge size; this edge prints on the bed
TOP_EDGE = "fillet" # "fillet" (rounder, first 2 layers overhang) or "chamfer" (prints perfectly)
BASE_CHAMFER = 0.6
SAC = 0.2           # sacrificial layer over counterbores printed on the bed (poke through)

# Screws: ISO 7380 M3 button head (head dia 5.7, height 1.65), tapped straight into PETG
PILOT_D = 2.6       # printed ~2.45 -> good thread bite for M3 in PETG
PILOT_CSK = 0.4     # 45 deg countersink at the pilot mouth (keeps the raised crater below hard-stop faces)
SCREW_CLEAR_D = 3.4
SCREW_HEAD_D = 6.4  # counterbore for the 5.7 mm button head
SCREW_HEAD_CB = 2.0 # counterbore depth (head 1.65 -> sits 0.35 below the surface)
HEAD_D, HEAD_H = 5.7, 1.65
PILLAR_D = 8.0
PILLAR_SEAL_D = 14.0      # pillars inside the sealed chamber (carry a gasket loop)
PILLAR_PILOT_L = 8.0      # M3x10: head seat z=2 -> tip z=12 -> 7 mm engaged, 1 mm spare
LUG_TOP = 20.0            # short base-screw lugs in the bay stay below the devkit (z 22.5) and the mic ring

# --------------------------------------------------------------------------
# Parameters: components (measurements + photo estimates)
# --------------------------------------------------------------------------
PB_L, PB_W, PB_T = 60.0, 40.0, 2.0       # perfboard 40 x 60 x 2
PB_HOLE_U_INSET = 2.5                     # MEASURED: holes 55 mm apart on the long side
PB_HOLE_W_INSET = 2.5                     # (photo) corner hole centre from the long edges
PB_HOLE_D = 2.0                           # (EST) corner hole diameter

DK_W = 25.5
DK_W0 = 2.0                               # (photo) header solder row at w~3.2 from u~5.4
DK_U0, DK_U1 = 0.5, 63.0
DK_STANDOFF = 8.5                         # (EST) female headers
DK_PCB_T = 1.6
USB_OVERHANG = 2.0
MOD_U0, MOD_U1 = 43.5, 69.0               # WROOM-1 incl. antenna overhang (measured: 9 mm past the edge)
MOD_W, MOD_T = 18.0, 3.2

DAC_U0, DAC_U1 = 10.0, 28.0               # (EST from photos)
DAC_W1 = PB_W + 13.0
DAC_LEN = 20.0                            # (EST)
DAC_SPACER = 2.5                          # (EST)
TERM_H = 10.0                             # (EST)

HW_U0, HW_U1 = -8.9, 6.6                  # MEASURED: PD board front edge 8.9 mm past the perfboard USB edge
HW_W0, HW_W1 = 8.25, 20.25                # MEASURED: PCB 12 mm wide, centred on the old port position
HW_DROP = 5.3                             # receptacle bottom below the perfboard underside
HW_ENV_H = 4.5                            # MEASURED: PCB + receptacle envelope height
HW_PCB_OVERSHOOT = 0.5                    # (EST) PCB edge in front of the receptacle face
USBC_W, USBC_H = 8.94, 3.26

SPK = 40.0                                # MEASURED square flange
SPK_DEPTH = 22.0                          # MEASURED overall depth
SPK_FLANGE_T = 1.0                        # MEASURED
SPK_FRONT = 0.5                           # MEASURED: surround / dust cap stand 0.5 mm in front of the flange
SPK_BODY_D = 40.0                         # MEASURED: round body directly behind the flange (incl. terminal)
SPK_BODY_RING = 6.0                       # (EST) depth of the 40 mm ring before the body steps down
SPK_MAGNET_D = 30.0                       # (EST)
SPK_SURROUND_D = 36.0                     # (EST) outer diameter of the rubber surround -> gasket rib sits outside
SPK_HOLE_PITCH = 32.0                     # MEASURED
SPK_HOLE_D = 3.2

MIC_D, MIC_T = 14.0, 1.6                  # INMP441 breakout
MIC_ROW = 4.0                             # MEASURED: pin rows 8 mm apart (+-4 from centre)
MIC_NOTCH_W = 2.0                         # MEASURED notch width; 12.5 mm across the notches (MEASURED)
MIC_ACROSS = 12.5
WIRE_D = 1.5                              # MEASURED wire outer diameter

STRIP_W = 12.0                            # MEASURED bare strip width (144 LED/m, 5 V)
STRIP_W_TOL = 1.0
STRIP_T = 2.0 + 0.5
CORE_R = 10.0

# --------------------------------------------------------------------------
# Parameters: layout
# --------------------------------------------------------------------------
ANT_CLEAR = 5.0
PB_SIDE_CLEAR_L = 3.0     # was 9: the mic no longer sits over the bay's left side
PB_SIDE_CLEAR_R = 4.0     # was 2.5: speaker wires must bend out of the amp terminal (faces the divider)
USB_RECESS = 0.3
STANDOFF_H = 7.0
STANDOFF_D = 4.6
STAKE_PIN_PROUD = 3.0
FLUSH_PINS = [(PB_HOLE_U_INSET, PB_HOLE_W_INSET)]
SPK_CABLE = 3.0           # 2-3 mm between speaker and divider for the terminal wires
SPK_CLEAR = 1.0           # other three sides

# speaker on top: thick chamber ceiling so M3x8 gets a full-depth pilot; bosses = hard stop for the flange
SPK_CEIL_T = 6.5
SPK_STANDOFF = 3.0        # ceiling -> flange front face (2.5 mm air in front of the cone)
BOSS_D = 6.2
SPK_PILOT_D = 2.6         # M3 (as printed). FALLBACK if an M3 head will not sit flat beside the speaker body: M2.5x8 -> 2.1
SPK_PILOT_L = 8.3         # M3x8 through the 1 mm flange -> 7 mm engaged, 1.3 mm spare, 1.2 mm skin on top
GRILLE_R, GRILLE_HOLE, GRILLE_PITCH = 15.5, 2.0, 3.0

# chamber gasket (TPU) + groove (base plate)
GROOVE_W, GROOVE_D = 2.0, 1.6
GK_BASE_W, GK_BASE_H = 1.6, 1.2
GK_RIB_W, GK_RIB_H = 0.8, 0.9                               # total 2.1 -> 0.5 proud
GK_LOOP_R = 4.8

# speaker gasket (TPU)
SG_RIB_R, SG_RIB_W, SG_RIB_H = 18.75, 0.7, 0.9
SG_COMPRESSION = 0.5

# mic ring on the front wall (board's labelled/port side faces the wall)
PORT_BOSS_D, PORT_BOSS_H = 5.4, 1.6       # was 6.0: more room for the solder joints on the labelled side
MIC_GK_OD, MIC_GK_ID, MIC_GK_T, MIC_GK_POCKET = 4.6, 2.2, 0.9, 0.6
MIC_PORT_D, MIC_PORT_CSK_D = 2.0, 3.6
MIC_SHOULDER_R0 = 6.0                     # rim support ring r 6.0..bore (solder joints end at r ~5.5)
MIC_BORE_R = MIC_D / 2 + 0.2
MIC_RING_T = 1.6
MIC_PIN_D = 1.7                           # truncated teardrop (prints sideways): flat top stays inside the notch
MIC_PIN_PROUD = 3.0                       # 1.7 x pin diameter above the board -> ~3.6 mm head
MIC_STAKE_HEAD_D = 3.6
GROMMET_D = 5.3
GROMMET_WIRE_D = 1.4                      # 1.5 mm wire, 0.05 mm squeeze per side

# plinth (PCTG light band) - kept unchanged from V1.2 (all values below are V1.2's)
PL_W, PL_D = 103.7, 75.6
PL_WALL = 1.6
PL_GAP = 3.5
PL_FLOOR = 1.6
PL_H = PL_FLOOR + 1.0 + STRIP_W + STRIP_W_TOL + 1.4
PL_R = 6.0
PL_COL_D = 13.0
PL_CORE = 7.6             # core outer face, inset from the plinth outline
FOOT_D, FOOT_H = 16.0, 3.0
FOOT_PEG_D, FOOT_PEG_OFF, FOOT_PEG_L = 2.6, 4.7, 2.0

# --------------------------------------------------------------------------
# derived
# --------------------------------------------------------------------------
W_E = PB_SIDE_CLEAR_L + DAC_W1 + PB_SIDE_CLEAR_R
W_S = SPK + SPK_CABLE + SPK_CLEAR
W = 3 * WALL + W_E + W_S
Y_PB0 = WALL + ANT_CLEAR + MOD_U1
D = Y_PB0 - HW_U0 + USB_RECESS
H_IN = 44.0
Z_IN0 = BASE_T
Z_IN1 = BASE_T + H_IN
H = Z_IN1 + TOP_T
X_PB0 = WALL + PB_SIDE_CLEAR_L
Z_PB0 = BASE_T + STANDOFF_H
X_DIV0 = WALL + W_E
X_CH0 = X_DIV0 + WALL

Z_CEIL = H - SPK_CEIL_T                       # chamber ceiling
Z_FL_FRONT = Z_CEIL - SPK_STANDOFF            # speaker flange front face (sits on the bosses)
Z_FL_BACK = Z_FL_FRONT - SPK_FLANGE_T
SPK_CX = X_CH0 + SPK_CABLE + SPK / 2
SPK_CY = 47.5
SPK_SCREWS = [(SPK_CX + sx * SPK_HOLE_PITCH / 2, SPK_CY + sy * SPK_HOLE_PITCH / 2)
              for sx in (-1, 1) for sy in (-1, 1)]

MIC_X, MIC_Z = 52.0, 38.0
Y_MIC_PORT = WALL + PORT_BOSS_H               # labelled face of the mic board
Y_MIC_BACK = Y_MIC_PORT + MIC_T               # component face (wires leave here)
MIC_NOTCH_R = ((MIC_NOTCH_W / 2) ** 2 + ((MIC_D - MIC_ACROSS) / 2) ** 2) / (MIC_D - MIC_ACROSS)
MIC_NOTCH_C = MIC_ACROSS / 2 + MIC_NOTCH_R    # notch circle centre radius (= pin axis)
MIC_PINS = [(MIC_X + s * MIC_NOTCH_C, MIC_Z) for s in (-1, 1)]

PL_X0, PL_Y0 = (W - PL_W) / 2, (D - PL_D) / 2   # plinth centred under the case
FEET = [(PL_X0 + 16.0, PL_Y0 + 18.0), (PL_X0 + PL_W - 16.0, PL_Y0 + 18.0),
        (PL_X0 + 16.0, PL_Y0 + PL_D - 18.0), (PL_X0 + PL_W - 16.0, PL_Y0 + PL_D - 18.0)]
LED_NOTCH_X = (PL_X0 + 25.0, PL_X0 + 41.0)        # core notch at the back
LED_SLOT = (X_PB0 + PB_W + 1.6, X_PB0 + PB_W + 11.6, 26.0, 44.0)   # x0, x1, y0, y1 (base plate)

GROMMET_Y, GROMMET_Z = Y_PB0 - (DAC_U0 + DAC_U1) / 2, 30.0      # in line with the amp terminal

# base plate -> shell screws: all inside the plinth outline (hidden by the plinth)
_cr = PL_R - SCREW_HEAD_D / 2 - 0.5          # corner screws: counterbore stays 0.5 inside the plinth corner arc
_cx = PL_X0 + PL_W - PL_R + _cr / math.sqrt(2)
SCREWS = {  # name: (x, y, kind)   kind: lug = short block, pillar = full height, seal = in the chamber
    "lug_front": (38.0, 9.0, "lug"),
    "lug_divider": (X_DIV0 - 4.0, 9.0, "lug"),
    "div_back": (X_DIV0 - 4.0, D - PL_Y0 - 4.0, "pillar"),
    "ch_front": (_cx, PL_Y0 + PL_R - _cr / math.sqrt(2), "seal"),
    "ch_back": (_cx, PL_Y0 + PL_D - PL_R + _cr / math.sqrt(2), "seal"),
}
SEAL_SCREWS = [(x, y) for (x, y, k) in SCREWS.values() if k == "seal"]

C = {  # render colours
    "case": "#3b4048", "base": "#2b2f35", "tpu": "#e8873a", "pctg": "#bfe6ff",
    "pcb": "#2f8a4c", "devkit": "#1d2536", "module": "#b9bec6", "dac": "#7a4bb5",
    "term": "#39b36f", "hw398": "#44484f", "usb": "#d9dde2", "spk": "#1b1b1b",
    "spk_cone": "#555a61", "mic": "#101820", "led": "#fff2a8", "ko": "#e0564a",
}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def box(x0, x1, y0, y1, z0, z1):
    return Pos(x0, y0, z0) * Box(x1 - x0, y1 - y0, z1 - z0, align=(Align.MIN, Align.MIN, Align.MIN))


def cyl_z(x, y, z0, z1, d):
    return Pos(x, y, z0) * Cylinder(d / 2, z1 - z0, align=(Align.CENTER, Align.CENTER, Align.MIN))


def cyl_x(y, z, x0, x1, d):
    return Pos((x0 + x1) / 2, y, z) * Rot(0, 90, 0) * Cylinder(d / 2, abs(x1 - x0))


def cyl_y(x, z, y0, y1, d):
    return Pos(x, (y0 + y1) / 2, z) * Rot(90, 0, 0) * Cylinder(d / 2, abs(y1 - y0))


def pilot_z(x, y, z_mouth, depth, direction=+1, d=None):
    """pilot hole going from a face at z_mouth into the material (+1 = upward), countersunk mouth"""
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


def inset(i, z0, z1, r):
    return rr(i, W - i, i, D - i, z0, z1, r)


def pinset(i, z0, z1, r):
    """V1.2 plinth geometry: inset(i) of the V1.2 case (plinth outline = inset 5) -> placed on the V2 plinth"""
    o = i - 5.0
    return rr(PL_X0 + o, PL_X0 + PL_W - o, PL_Y0 + o, PL_Y0 + PL_D - o, z0, z1, r)


def teardrop_y(x, z, y0, y1, d):
    """horizontal cylinder along Y with a 45 deg point towards +Z (= the bed when the shell prints upside down)"""
    r = d / 2
    wedge = Pos(x, (y0 + y1) / 2, z + r / math.sqrt(2)) * Rot(0, 45, 0) * Box(r, abs(y1 - y0), r)
    return cyl_y(x, z, y0, y1, d) + wedge


def pb(u, w, zl=0.0):
    """perfboard-local -> case coordinates (proper rotation: u -> -Y, w -> +X)"""
    return (X_PB0 + w, Y_PB0 - u, Z_PB0 + zl)


def pb_box(u0, u1, w0, w1, z0, z1):
    xa, ya, za = pb(u0, w0, z0)
    xb, yb, zb = pb(u1, w1, z1)
    return box(min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb), min(za, zb), max(za, zb))


def usbc(face, length):
    x, y, z = face
    r = USBC_H / 2
    body = box(x - USBC_W / 2 + r, x + USBC_W / 2 - r, y - length, y, z - r, z + r)
    for ex in (x - USBC_W / 2 + r, x + USBC_W / 2 - r):
        body += cyl_y(ex, z, y - length, y, USBC_H)
    return body


def lug_solid(x0, x1, y0, y1, z0, z1):
    """block on the front wall whose top rises at 45 deg towards the wall: prints without support
    when the shell is upside down (the flat top would be a 10 mm overhang)"""
    pts = [(y0, z0), (y1, z0), (y1, z1), (y0, z1 + (y1 - y0))]
    return extrude(Plane.YZ.offset(x0) * Polygon(*pts, align=None), amount=x1 - x0)


def union(shapes):
    out = None
    for s in shapes:
        out = s if out is None else out + s
    return out


CHAMBER_OUTLINE = (X_CH0, W - WALL, WALL, D - WALL, R_VERT - WALL)
PLINTH_OUTLINE = (PL_X0, PL_X0 + PL_W, PL_Y0, PL_Y0 + PL_D, PL_R)


# --------------------------------------------------------------------------
# Components (not printed) + keep-outs
# --------------------------------------------------------------------------
def mic_board():
    b = cyl_y(MIC_X, MIC_Z, Y_MIC_PORT, Y_MIC_BACK, MIC_D)
    for (px, pz) in MIC_PINS:
        b -= cyl_y(px, pz, Y_MIC_PORT - 1, Y_MIC_BACK + 1, 2 * MIC_NOTCH_R)
    b += box(MIC_X - 1.8, MIC_X + 1.8, Y_MIC_BACK, Y_MIC_BACK + 1.0, MIC_Z - 1.4, MIC_Z + 1.4)   # MEMS can
    return b


def mic_pin_positions():
    """rows perpendicular to the notch axis: x = +-MIC_ROW, pins at z 0 / +-2.54"""
    return [(MIC_X + sx * MIC_ROW, MIC_Z + dz) for sx in (-1, 1) for dz in (-2.54, 0.0, 2.54)]


def components():
    parts = {}
    board = pb_box(0, PB_L, 0, PB_W, 0, PB_T)
    for (u, w) in [(u, w) for u in (PB_HOLE_U_INSET, PB_L - PB_HOLE_U_INSET) for w in (PB_HOLE_W_INSET, PB_W - PB_HOLE_W_INSET)]:
        x, y, z = pb(u, w)
        board -= cyl_z(x, y, z - 1, z + PB_T + 1, PB_HOLE_D)
    parts["perfboard"] = (board, C["pcb"])
    z_dk = PB_T + DK_STANDOFF
    parts["devkit"] = (pb_box(DK_U0, DK_U1, DK_W0, DK_W0 + DK_W, z_dk, z_dk + DK_PCB_T), C["devkit"])
    wmc = DK_W0 + DK_W / 2
    parts["wroom_module"] = (pb_box(MOD_U0, MOD_U1, wmc - MOD_W / 2, wmc + MOD_W / 2,
                                    z_dk + DK_PCB_T, z_dk + DK_PCB_T + MOD_T), C["module"])
    parts["devkit_usbc"] = (union([usbc(pb(-USB_OVERHANG, wc, z_dk + DK_PCB_T + USBC_H / 2), 7.5)
                                   for wc in (wmc - 5.5, wmc + 5.5)]), C["usb"])
    z_dac = PB_T + DAC_SPACER
    parts["dac"] = (pb_box(DAC_U0, DAC_U1, DAC_W1 - DAC_LEN, DAC_W1, z_dac, z_dac + 1.6), C["dac"])
    uc = (DAC_U0 + DAC_U1) / 2
    parts["dac_terminal"] = (pb_box(uc - 5, uc + 5, DAC_W1 - 8, DAC_W1 - 0.5, z_dac + 1.6, z_dac + TERM_H), C["term"])
    z_env_top = -HW_DROP + HW_ENV_H
    parts["hw398"] = (pb_box(HW_U0, HW_U1, HW_W0, HW_W1, z_env_top - 1.0, z_env_top), C["hw398"])
    hwc = (HW_W0 + HW_W1) / 2
    parts["hw398_usbc"] = (usbc(pb(HW_U0 + HW_PCB_OVERSHOOT, hwc, -HW_DROP + USBC_H / 2), 7.5), C["usb"])

    # speaker, cone up, flange on the ceiling bosses
    flange = Pos(SPK_CX, SPK_CY, Z_FL_BACK) * extrude(RectangleRounded(SPK, SPK, 4), amount=SPK_FLANGE_T)
    for (sx, sy) in SPK_SCREWS:
        flange -= cyl_z(sx, sy, Z_FL_BACK - 1, Z_FL_FRONT + 1, SPK_HOLE_D)
    z_bottom = Z_FL_FRONT - SPK_DEPTH
    ring = cyl_z(SPK_CX, SPK_CY, Z_FL_BACK - SPK_BODY_RING, Z_FL_BACK + 0.01, SPK_BODY_D)
    magnet = cyl_z(SPK_CX, SPK_CY, z_bottom, Z_FL_BACK - SPK_BODY_RING + 0.01, SPK_MAGNET_D)
    parts["speaker"] = (flange + ring + magnet, C["spk"])
    parts["speaker_cone"] = (cyl_z(SPK_CX, SPK_CY, Z_FL_FRONT - 0.01, Z_FL_FRONT + SPK_FRONT, SPK_SURROUND_D), C["spk_cone"])
    # keep-out: terminal wires on the divider side of the body (2-3 mm)
    parts["spk_cable_keepout"] = (box(X_CH0 + 0.1, SPK_CX - SPK_BODY_D / 2, SPK_CY - 5, SPK_CY + 5,
                                      Z_FL_BACK - 12, Z_FL_BACK - 0.01), C["ko"])
    # keep-out: screw heads under the flange + straight 2 mm hex key paths down to the open bottom
    parts["spk_screw_heads"] = (union([cyl_z(sx, sy, Z_FL_BACK - HEAD_H, Z_FL_BACK, HEAD_D) for (sx, sy) in SPK_SCREWS]), C["ko"])
    parts["spk_key_paths"] = (union([cyl_z(sx, sy, BASE_T - 30, Z_FL_BACK - HEAD_H - 0.01, 2.4) for (sx, sy) in SPK_SCREWS]), C["ko"])

    # mic on the front wall
    parts["mic"] = (mic_board(), C["mic"])
    ko = None
    for (px, pz) in mic_pin_positions():
        c = cyl_y(px, pz, Y_MIC_BACK, Y_MIC_BACK + 10, 2.0) + cyl_y(px, pz, Y_MIC_PORT - 1.0, Y_MIC_PORT, 1.6)
        ko = c if ko is None else ko + c
    parts["mic_wires_keepout"] = (ko, C["ko"])
    parts["mic_stake_heads"] = (union([cyl_y(px, pz, Y_MIC_BACK, Y_MIC_BACK + 1.2, MIC_STAKE_HEAD_D)
                                       for (px, pz) in MIC_PINS]), "#8a919c")

    # LED pigtail (3 x 1.5 mm wires) through the base-plate slot into the plinth core
    x0, x1, y0, y1 = LED_SLOT
    xc, yc = (x0 + x1) / 2, (y0 + y1) / 2
    parts["led_wires_keepout"] = (box(xc - 2.5, xc + 2.5, yc - 1.5, yc + 1.5, -PL_H + PL_FLOOR + 0.5, BASE_T + 4), C["ko"])

    z0 = -PL_H + PL_FLOOR + 1.0 + STRIP_W_TOL / 2
    strip = pinset(12.6 - (STRIP_T - 0.5), z0, z0 + STRIP_W, CORE_R + STRIP_T - 0.5) - \
        pinset(12.6, z0 - 1, z0 + STRIP_W + 1, CORE_R)
    strip -= box(LED_NOTCH_X[0], LED_NOTCH_X[1], PL_Y0 + PL_D / 2, D + 1, z0 - 1, z0 + STRIP_W + 1)
    parts["led_strip"] = (strip, C["led"])
    return parts


# --------------------------------------------------------------------------
# Printed parts
# --------------------------------------------------------------------------
def shell():
    outer = rr(0, W, 0, D, BASE_T, H, R_VERT)
    top = outer.edges().group_by(Axis.Z)[-1]
    outer = fillet(top, radius=R_TOP) if TOP_EDGE == "fillet" else chamfer(top, length=R_TOP)
    r_in = R_VERT - WALL
    bay = rr(WALL, X_DIV0, WALL, D - WALL, BASE_T - 1, Z_IN1, r_in)
    chamber = rr(X_CH0, W - WALL, WALL, D - WALL, BASE_T - 1, Z_CEIL, r_in)
    s = outer - bay - chamber

    # base-plate screw receivers (all hidden under the plinth)
    for name, (x, y, kind) in SCREWS.items():
        if kind == "lug":
            x0 = x - 4.0
            x1 = X_DIV0 + 0.1 if name == "lug_divider" else x + 4.0
            s += lug_solid(x0, x1, WALL - 0.1, y + 4.0, BASE_T, LUG_TOP)
        elif kind == "pillar":
            s += cyl_z(x, y, BASE_T, Z_IN1 + 0.1, PILLAR_D)
            s += box(x, X_DIV0 + 0.1, y - PILLAR_D / 2, D - WALL + 0.1, BASE_T, Z_IN1 + 0.1)   # web to divider + back wall
        else:
            s += cyl_z(x, y, BASE_T, Z_CEIL + 0.1, PILLAR_SEAL_D) & outer
        s -= pilot_z(x, y, BASE_T, PILLAR_PILOT_L, +1)

    # speaker bosses hanging from the ceiling (hard stop for the flange) + blind pilots
    for (sx, sy) in SPK_SCREWS:
        s += cyl_z(sx, sy, Z_FL_FRONT, Z_CEIL + 0.1, BOSS_D)
        s -= pilot_z(sx, sy, Z_FL_FRONT, SPK_PILOT_L, +1, SPK_PILOT_D)

    # speaker grille: hex hole field in the top face
    n = int(GRILLE_R // GRILLE_PITCH) + 2
    holes = []
    for j in range(-n, n + 1):
        for i in range(-n, n + 1):
            hx = SPK_CX + (i + 0.5 * (j % 2)) * GRILLE_PITCH
            hy = SPK_CY + j * GRILLE_PITCH * math.sqrt(3) / 2
            if math.hypot(hx - SPK_CX, hy - SPK_CY) <= GRILLE_R - GRILLE_HOLE / 2:
                holes.append(cyl_z(hx, hy, Z_CEIL - 0.1, H + 1, GRILLE_HOLE))
    s -= union(holes)

    # USB-C (PD board) cutout, open to the bottom edge
    xa, _, _ = pb(0, (HW_W0 + HW_W1) / 2)
    cw = (HW_W1 - HW_W0) + 0.6
    z_top = Z_PB0 - HW_DROP + HW_ENV_H + 0.3
    s -= box(xa - cw / 2, xa + cw / 2, D - WALL - 1, D + 1, BASE_T - 1, z_top)

    # speaker wire pass-through in the divider (TPU grommet), in line with the amp terminal
    s -= cyl_x(GROMMET_Y, GROMMET_Z, X_DIV0 - 1, X_CH0 + 1, 5.0)

    # mic ring on the front wall: port boss + gasket pocket, rim shoulder, ring, two stake pins
    y_w = WALL - 0.1
    s += teardrop_y(MIC_X, MIC_Z, y_w, Y_MIC_BACK, 2 * (MIC_BORE_R + MIC_RING_T))
    s -= cyl_y(MIC_X, MIC_Z, Y_MIC_PORT, Y_MIC_BACK + 1, 2 * MIC_BORE_R)                   # bore for the board
    s -= ring_y(MIC_X, MIC_Z, WALL, Y_MIC_PORT + 0.01, PORT_BOSS_D / 2, MIC_SHOULDER_R0)    # pocket for solder joints
    s -= cyl_y(MIC_X, MIC_Z, Y_MIC_PORT - MIC_GK_POCKET, Y_MIC_PORT + 0.01, MIC_GK_OD + 0.2)
    for (px, pz) in MIC_PINS:
        r = MIC_PIN_D / 2
        s += teardrop_y(px, pz, y_w, Y_MIC_BACK + MIC_PIN_PROUD, MIC_PIN_D) & \
            box(px - 2, px + 2, y_w - 1, Y_MIC_BACK + MIC_PIN_PROUD + 1, pz - 2, pz + r)
    s -= cyl_y(MIC_X, MIC_Z, -1, Y_MIC_PORT, MIC_PORT_D)                                    # acoustic port
    csk_h = (MIC_PORT_CSK_D - MIC_PORT_D) / 2
    s -= Pos(MIC_X, csk_h - 0.01, MIC_Z) * Rot(90, 0, 0) * \
        Cone(MIC_PORT_D / 2, MIC_PORT_CSK_D / 2 + 0.01, csk_h + 0.02, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return s


def groove_solid(z0, z1):
    g = rr_band(CHAMBER_OUTLINE, -GROOVE_W / 2, GROOVE_W / 2, z0, z1)
    for (x, y) in SEAL_SCREWS:
        g += ring_z(x, y, z0, z1, GK_LOOP_R - GROOVE_W / 2, GK_LOOP_R + GROOVE_W / 2)
    return g


def base_plate():
    b = rr(0, W, 0, D, 0, BASE_T, R_VERT)
    b = chamfer(b.edges().group_by(Axis.Z)[0], length=BASE_CHAMFER)
    for (x, y, _) in SCREWS.values():
        b -= cyl_z(x, y, SCREW_HEAD_CB + SAC, BASE_T + 1, SCREW_CLEAR_D)
        b -= cyl_z(x, y, -1, SCREW_HEAD_CB, SCREW_HEAD_D)
    for (fx, fy) in FEET:                                   # plinth screws M3x20 from below (under the feet)
        b += cyl_z(fx, fy, BASE_T - 0.1, BASE_T + 3.0, 9.0)
        b -= pilot_z(fx, fy, 0.0, 6.0, +1)
    for (u, w) in [(u, w) for u in (PB_HOLE_U_INSET, PB_L - PB_HOLE_U_INSET) for w in (PB_HOLE_W_INSET, PB_W - PB_HOLE_W_INSET)]:
        x, y, _ = pb(u, w)
        b += cyl_z(x, y, BASE_T - 0.1, Z_PB0, STANDOFF_D)
        proud = 0.0 if (u, w) in FLUSH_PINS else STAKE_PIN_PROUD
        b += cyl_z(x, y, Z_PB0 - 0.1, Z_PB0 + PB_T + proud, PB_HOLE_D - 0.25)
    xa, _, _ = pb(0, (HW_W0 + HW_W1) / 2)
    cw = (HW_W1 - HW_W0) + 0.6
    b += box(xa - cw / 2 + 0.3, xa + cw / 2 - 0.3, D - WALL, D, BASE_T - 0.1, Z_PB0 - HW_DROP - 0.3)
    b -= groove_solid(BASE_T - GROOVE_D, BASE_T + 1)
    x0, x1, y0, y1 = LED_SLOT
    b -= rr(x0, x1, y0, y1, -1, BASE_T + 4, 2.0)
    return b


def chamber_gasket():
    z0 = BASE_T - GROOVE_D
    g = rr_band(CHAMBER_OUTLINE, -GK_BASE_W / 2, GK_BASE_W / 2, z0, z0 + GK_BASE_H)
    rib = rr_band(CHAMBER_OUTLINE, 0.0, GK_RIB_W, z0 + GK_BASE_H - 0.01, z0 + GK_BASE_H + GK_RIB_H)
    for (x, y) in SEAL_SCREWS:
        g += ring_z(x, y, z0, z0 + GK_BASE_H, GK_LOOP_R - GK_BASE_W / 2, GK_LOOP_R + GK_BASE_W / 2)
        rib += ring_z(x, y, z0 + GK_BASE_H - 0.01, z0 + GK_BASE_H + GK_RIB_H, GK_LOOP_R - GK_RIB_W / 2,
                      GK_LOOP_R + GK_RIB_W / 2)
    return g + rib


def speaker_gasket():
    """flat TPU frame between ceiling and flange, keyed around the 4 bosses; rib presses on the flange
    outside the rubber surround. Bosses are the hard stop -> rib squeeze = SG_COMPRESSION."""
    z_body = Z_FL_FRONT + SG_RIB_H - SG_COMPRESSION
    body = Pos(SPK_CX, SPK_CY, z_body) * extrude(RectangleRounded(SPK, SPK, 4), amount=Z_CEIL - z_body)
    body -= cyl_z(SPK_CX, SPK_CY, z_body - 1, Z_CEIL + 1, 2 * SG_RIB_R - SG_RIB_W - 0.2)
    rib = ring_z(SPK_CX, SPK_CY, z_body - SG_RIB_H, z_body + 0.01, SG_RIB_R - SG_RIB_W / 2, SG_RIB_R + SG_RIB_W / 2)
    g = body + rib
    for (sx, sy) in SPK_SCREWS:
        g -= cyl_z(sx, sy, z_body - 2, Z_CEIL + 1, BOSS_D + 0.6)
    return g


def mic_gasket():
    return ring_y(MIC_X, MIC_Z, Y_MIC_PORT - MIC_GK_POCKET, Y_MIC_PORT - MIC_GK_POCKET + MIC_GK_T,
                  MIC_GK_ID / 2, MIC_GK_OD / 2)


def plinth():
    """V1.2 plinth, unchanged (only placed on the V2 case)"""
    z0, z1 = -PL_H, 0.0
    p = pinset(5.0, z0, z1, PL_R) - pinset(5.0 + PL_WALL, z0 + PL_FLOOR, z1 + 1, PL_R - PL_WALL)
    core = pinset(12.6, z0 + PL_FLOOR - 0.1, z1, CORE_R) - pinset(12.6 + PL_WALL, z0, z1 + 1, CORE_R - PL_WALL)
    core -= box(LED_NOTCH_X[0] + 2, LED_NOTCH_X[1] - 2, PL_Y0 + PL_D / 2, PL_Y0 + PL_D + 5, z0 + PL_FLOOR, z1 + 1)
    p += core
    for (fx, fy) in FEET:
        p += cyl_z(fx, fy, z0, z1, PL_COL_D)
        p -= cyl_z(fx, fy, z0 + SCREW_HEAD_CB + SAC, z1 + 1, SCREW_CLEAR_D)
        p -= cyl_z(fx, fy, z0 - 1, z0 + SCREW_HEAD_CB, SCREW_HEAD_D)
        for sx in (-1, 1):
            p -= cyl_z(fx + sx * FOOT_PEG_OFF, fy, z0 - 1, z0 + FOOT_PEG_L + 0.4, FOOT_PEG_D)
    return p


def grommet():
    body = cyl_x(GROMMET_Y, GROMMET_Z, X_DIV0 - 0.01, X_CH0 + 0.01, GROMMET_D)
    flange = cyl_x(GROMMET_Y, GROMMET_Z, X_CH0, X_CH0 + 1.2, 9.0)
    barb = Pos(X_DIV0, GROMMET_Y, GROMMET_Z) * Rot(0, -90, 0) * Cone(3.0, 2.5, 0.8, align=(Align.CENTER, Align.CENTER, Align.MIN))
    g = body + flange + barb
    for sy in (-1, 1):
        g -= cyl_x(GROMMET_Y + sy * 1.35, GROMMET_Z, X_DIV0 - 2, X_CH0 + 3, GROMMET_WIRE_D)
    return g


def feet():
    f = None
    for (fx, fy) in FEET:
        foot = cyl_z(fx, fy, -PL_H - FOOT_H, -PL_H, FOOT_D)
        foot = fillet(foot.edges().group_by(Axis.Z)[0], radius=1.0)
        for sx in (-1, 1):
            foot += cyl_z(fx + sx * FOOT_PEG_OFF, fy, -PL_H - 0.01, -PL_H + FOOT_PEG_L, FOOT_PEG_D)
        f = foot if f is None else f + foot
    return f


def build():
    comps = components()
    case = {
        "shell": (shell(), C["case"]),
        "base_plate": (base_plate(), C["base"]),
        "plinth_PCTG": (plinth(), C["pctg"]),
        "chamber_gasket_TPU": (chamber_gasket(), C["tpu"]),
        "speaker_gasket_TPU": (speaker_gasket(), C["tpu"]),
        "mic_gasket_TPU": (mic_gasket(), C["tpu"]),
        "feet_TPU": (feet(), C["tpu"]),
        "grommet_TPU": (grommet(), C["tpu"]),
    }
    return comps, case


# print orientation: (rotation, how many to print, material)
PRINT = {
    "shell": ("flip", 1, "PETG black - top face on the bed, no supports"),
    "base_plate": ("asis", 1, "PETG black - as modelled, no supports"),
    "plinth_PCTG": ("asis", 1, "PCTG clear - light band (unchanged since V1.2)"),
    "chamber_gasket_TPU": ("asis", 1, "TPU black - flat"),
    "speaker_gasket_TPU": ("flip", 1, "TPU black - flat face down, rib up"),
    "mic_gasket_TPU": ("y_down", 1, "TPU black - tiny ring, print 2-3 spares"),
    "feet_TPU": ("asis", 4, "TPU black - one foot, print 4"),
    "grommet_TPU": ("x_down", 1, "TPU black - flange on the bed, print 2 (spare)"),
}


def print_pose(name, shape):
    mode = PRINT[name][0]
    if name == "feet_TPU":
        fx, fy = FEET[0]
        shape = shape & box(fx - 10, fx + 10, fy - 10, fy + 10, -100, 100)
    if mode == "flip":
        shape = Rot(180, 0, 0) * shape
    elif mode == "x_down":
        shape = Rot(0, 90, 0) * shape          # chamber-side flange (high X) -> bottom
    elif mode == "y_down":
        shape = Rot(-90, 0, 0) * shape
    bb = shape.bounding_box()
    return Pos(-(bb.min.X + bb.max.X) / 2, -(bb.min.Y + bb.max.Y) / 2, -bb.min.Z) * shape


if __name__ == "__main__":
    import json
    comps, case = build()
    root = os.path.dirname(HERE)
    build_dir, stl_dir, step_dir = (os.path.join(root, d) for d in ("build", "stl", "step"))
    for d in (build_dir, stl_dir, step_dir):
        os.makedirs(d, exist_ok=True)
    children = []
    for name, (shape, col) in {**comps, **case}.items():
        shape.label = name
        shape.color = Color(col)
        children.append(shape)
        export_stl(shape, os.path.join(build_dir, f"{name}.stl"), tolerance=0.05, angular_tolerance=0.2)
    for name, (shape, _) in case.items():
        export_stl(print_pose(name, shape), os.path.join(stl_dir, f"{name}.stl"), tolerance=0.02, angular_tolerance=0.15)
    export_step(Compound(label="voice_satellite_V2", children=children), os.path.join(step_dir, "voice_satellite_v2_assembly.step"))
    info = {"W": round(W, 2), "D": round(D, 2), "H": round(H, 2), "H_total_incl_plinth_feet": round(H + PL_H + FOOT_H, 1),
            "overhang_x": round(PL_X0, 2), "overhang_y": round(PL_Y0, 2), "X_DIV0": round(X_DIV0, 2),
            "spk_c": (round(SPK_CX, 2), SPK_CY), "Z_CEIL": Z_CEIL, "flange_front": Z_FL_FRONT,
            "mic_pins": [(round(x, 2), z) for x, z in MIC_PINS], "notch_r": round(MIC_NOTCH_R, 3),
            "screws": {k: (round(v[0], 2), round(v[1], 2)) for k, v in SCREWS.items()}}
    print(json.dumps(info))
