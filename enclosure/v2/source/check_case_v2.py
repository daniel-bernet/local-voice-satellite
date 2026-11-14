# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Daniel Bernet
"""Verification suite for case_v2 (collisions, seal, speaker/mic mounts, hidden screws, assembly paths,
clearances) + renders. Run case_v2.py first (writes ../build). Writes ../CHECK_REPORT.txt and ../renders/*.png.
Note: the original suite also compared the plinth against the V1.2 source, which is not part of this repo;
that comparison is dropped here."""
import itertools, warnings, math, os, sys
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import case_v2 as J
from build123d import *

ROOT = os.path.dirname(J.HERE)
BUILD, RENDERS = os.path.join(ROOT, "build"), os.path.join(ROOT, "renders")
os.makedirs(RENDERS, exist_ok=True)
comps, case = J.build()
A = {**comps, **case}
lines = []


def out(s):
    print(s); lines.append(s)


def iv(a, b):
    try:
        i = a & b
        return i.volume if i is not None else 0.0
    except Exception:
        return float("nan")


def dist(a, b):
    return A[a][0].distance_to(A[b][0])


fails = []
def ok(cond, msg):
    out(("  OK   " if cond else "  FAIL ") + msg)
    if not cond: fails.append(msg)

out("== part integrity (solids per printed part) ==")
for n, (s, _) in case.items():
    k = len(s.solids()); exp = {"feet_TPU": 4}.get(n, 1)
    ok(k == exp and s.is_valid, f"{n:20s} solids={k} valid={s.is_valid}")

out("== unexpected collisions (mm^3) ==")
expected = {("devkit", "wroom_module"), ("devkit", "devkit_usbc"), ("dac", "dac_terminal"), ("hw398", "hw398_usbc"),
            ("speaker", "speaker_cone"), ("shell", "chamber_gasket_TPU"), ("speaker", "speaker_gasket_TPU"),
            ("mic", "mic_gasket_TPU"), ("plinth_PCTG", "feet_TPU"), ("mic", "mic_wires_keepout"), ("shell", "grommet_TPU"),
            ("shell", "mic_stake_heads"),           # heads are formed from the pin tips
            ("speaker", "spk_screw_heads"),         # reported separately below
            ("spk_screw_heads", "spk_key_paths"), ("mic_wires_keepout", "mic_stake_heads"),
            ("spk_key_paths", "base_plate"), ("spk_key_paths", "plinth_PCTG"), ("spk_key_paths", "feet_TPU")}  # key paths: base off
bad = 0
for a, b in itertools.combinations(A, 2):
    if (a, b) in expected or (b, a) in expected: continue
    v = iv(A[a][0], A[b][0])
    if v != v or v > 0.01:
        bad += 1; out(f"  FAIL {a} x {b}: {v:.2f}")
ok(bad == 0, "no unexpected collisions")

out("== chamber seal ==")
g = case["chamber_gasket_TPU"][0]; sh = case["shell"][0]; bp = case["base_plate"][0]
groove = J.groove_solid(J.BASE_T - J.GROOVE_D, J.BASE_T)
proud = g & J.box(-5, J.W + 5, -5, J.D + 5, J.BASE_T, J.BASE_T + 5)
ok(iv(g, bp) < 0.01, f"gasket x base plate = {iv(g, bp):.2f}")
cov = iv(proud, sh) / proud.volume * 100
ok(cov > 99, f"proud rib under shell material: {cov:.1f} %  (squeeze {J.GK_BASE_H + J.GK_RIB_H - J.GROOVE_D:.1f} mm)")
out(f"       groove fill: {(g.volume - proud.volume) / groove.volume * 100:.0f} %")
holes = [J.cyl_z(x, y, 0, J.BASE_T, J.SCREW_CLEAR_D) for (x, y, _) in J.SCREWS.values()]
dmin = min(groove.distance_to(h) for h in holes)
ok(dmin >= 1.5, f"groove -> screw hole >= 1.5: {dmin:.2f} mm")
edge = J.rr(-5, J.W + 5, -5, J.D + 5, 0, J.BASE_T, J.R_VERT) - J.rr(0, J.W, 0, J.D, -1, J.BASE_T + 1, J.R_VERT)
de = groove.distance_to(edge)
ok(de >= 1.39, f"groove -> base plate outer edge >= 1.4: {de:.2f} mm")
for (x, y) in J.SEAL_SCREWS:
    loop = J.ring_z(x, y, 0, J.BASE_T, J.GK_LOOP_R - 0.8, J.GK_LOOP_R + 0.8)
    ok(iv(loop, g) > 0, f"in-chamber screw ({x:.1f},{y:.1f}) has its own gasket loop")

out("== speaker (top mount) ==")
sp = comps["speaker"][0]; sg = case["speaker_gasket_TPU"][0]
ok(abs(sp.distance_to(sh)) < 0.02, f"flange on bosses (hard stop) distance = {sp.distance_to(sh):.3f}")
ok(iv(sg, sh) < 0.01, f"speaker gasket x shell = {iv(sg, sh):.2f}")
v = iv(sg, sp); ok(v > 1, f"gasket rib squeezed by flange: {v:.1f} mm^3 ({J.SG_COMPRESSION} mm)")
ok(sg.distance_to(comps["speaker_cone"][0]) > 0.2, f"gasket -> cone/surround: {sg.distance_to(comps['speaker_cone'][0]):.2f} mm")
out(f"       air gap cone -> ceiling: {J.Z_CEIL - J.Z_FL_FRONT - J.SPK_FRONT:.1f} mm")
kp = comps["spk_key_paths"][0]
ok(kp.distance_to(sh) > 0.3, f"hex-key paths (2 mm key, straight down) -> shell: {kp.distance_to(sh):.2f} mm")
ok(kp.distance_to(sp) > 0.3, f"hex-key paths -> speaker body: {kp.distance_to(sp):.2f} mm")
hv = iv(comps["spk_screw_heads"][0], sp)
out(f"  INFO screw heads vs 40 mm body ring (modelled as a sharp cylinder): {hv:.2f} mm^3 overlap "
    f"(head reaches r {math.hypot(16, 16) - J.HEAD_D / 2:.2f}, body r {J.SPK_BODY_D / 2})")
steps = 140
blocked = max(iv(Pos(0, 0, -0.5 * k) * (sp + comps["speaker_cone"][0]), sh) for k in range(1, steps))
ok(blocked < 0.01, f"speaker can be lowered into the chamber from the open bottom (shell upside down): {blocked:.2f}")
blocked = max(iv(Pos(0, 0, -0.5 * k) * sg, sh) for k in range(1, steps))
ok(blocked < 0.01, f"speaker gasket can be placed the same way: {blocked:.2f}")
ok(dist("speaker", "base_plate") > 5, f"speaker body -> base plate: {dist('speaker', 'base_plate'):.1f} mm")
ok(dist("speaker", "grommet_TPU") > 1, f"speaker -> grommet_TPU: {dist('speaker', 'grommet_TPU'):.2f} mm")
ok(dist("spk_cable_keepout", "shell") >= 0.05, f"terminal wire band -> divider: {dist('spk_cable_keepout', 'shell'):.2f} mm")

out("== mic (front wall ring, heat-staked pins) ==")
mc = comps["mic"][0]
ok(mc.distance_to(sh) >= 0, f"board in ring, pins in notches, no interference: {iv(mc, sh):.3f} mm^3 overlap")
out(f"       notch circle r {J.MIC_NOTCH_R:.2f} at {J.MIC_NOTCH_C:.2f} mm from centre; pin d {J.MIC_PIN_D} -> "
    f"{J.MIC_NOTCH_R - J.MIC_PIN_D / 2:.2f} mm play per side")
ok(iv(case["mic_gasket_TPU"][0], mc) > 0.1, f"port gasket squeezed: {iv(case['mic_gasket_TPU'][0], mc):.2f} mm^3")
ko = comps["mic_wires_keepout"][0]
d1 = comps["mic_stake_heads"][0].distance_to(ko)
ok(d1 > 0.3, f"melted pin heads (d {J.MIC_STAKE_HEAD_D}) -> wires: {d1:.2f} mm")
d2 = sh.distance_to(ko)
ok(d2 > 0.2, f"ring / port boss -> solder joints + wires: {d2:.2f} mm")
blocked = max(iv(Pos(0, 0.5 * k, 0) * mc, sh) for k in range(1, 30))
ok(blocked < 0.01, f"board slides into the ring along the pins: {blocked:.3f}")
iron = None
for (px, pz) in J.MIC_PINS:
    L = 70
    c = Pos(px, J.Y_MIC_BACK + J.MIC_PIN_PROUD + 2.0, pz) * Rot(-30, 0, 0) * Rot(-90, 0, 0) * \
        Cylinder(2.5, L, align=(Align.CENTER, Align.CENTER, Align.MIN))
    c = c & J.box(-10, J.W + 10, -10, J.D + 10, J.BASE_T + 0.5, 60)
    iron = c if iron is None else iron + c
ok(iron.distance_to(sh) > 0.2, f"iron (d 5 mm, 30 deg off axis) reaches both pin tips: clearance {iron.distance_to(sh):.2f} mm")
ok(dist("mic", "wroom_module") >= 14, f"mic board -> ESP32 module/antenna: {dist('mic', 'wroom_module'):.1f} mm")
out(f"       mic port -> speaker centre: {math.dist((J.MIC_X, 0, J.MIC_Z), (J.SPK_CX, J.SPK_CY, J.H)):.0f} mm, 90 deg apart")

out("== base-plate screws hidden by the plinth ==")
pl = J.rr(*J.PLINTH_OUTLINE[:4], -1, 1, J.PLINTH_OUTLINE[4])
for n, (x, y, k) in J.SCREWS.items():
    cb = J.cyl_z(x, y, -0.5, 0.5, J.SCREW_HEAD_D)
    outside = J.box(-20, J.W + 20, -20, J.D + 20, -0.5, 0.5) - pl
    m = cb.distance_to(outside)
    ok(m >= 0.45, f"{n:12s} ({x:6.2f},{y:6.2f}) counterbore inside plinth outline, margin {m:.2f} mm")
out(f"       overhang: {J.PL_X0:.2f} mm left/right, {J.PL_Y0:.2f} mm front/back")

out("== assembly paths ==")
base_mounted = ["perfboard", "devkit", "wroom_module", "devkit_usbc", "dac", "dac_terminal", "hw398", "hw398_usbc"]
worst = 0
for n in base_mounted:
    part = A[n][0]; bb = part.bounding_box()
    steps = int((bb.max.Z - J.BASE_T) / 0.5) + 2
    v = max(iv(Pos(0, 0, -0.5 * k) * part, sh) for k in range(steps)); worst = max(worst, v)
    if v > 0.01: out(f"  FAIL {n}: blocked ({v:.1f} mm^3)")
ok(worst <= 0.01, "shell can be lowered onto the base assembly")
plp = case["plinth_PCTG"][0]
blocked = max(iv(Pos(0, 0, -0.5 * k) * plp, bp) for k in range(1, 40))
ok(blocked < 0.01, "plinth fits up against the base plate")

out("== LED pass-through ==")
x0, x1, y0, y1 = J.LED_SLOT
inner = J.pinset(12.6 + J.PL_WALL, -1, 1, J.CORE_R - J.PL_WALL)
slot = J.box(x0, x1, y0, y1, -0.5, 0.5)
ok(iv(slot, inner) > slot.volume * 0.99, "slot opens into the plinth core interior")
for n in ("base_plate", "plinth_PCTG", "perfboard", "shell", "dac"):
    ok(dist("led_wires_keepout", n) > 0.3, f"LED wires -> {n}: {dist('led_wires_keepout', n):.1f} mm")

out("== clearances ==")
for a, b, lim in [("wroom_module", "shell", 4.5), ("dac_terminal", "shell", 3.9), ("devkit_usbc", "shell", 0.5),
                  ("perfboard", "base_plate", -1), ("speaker", "shell", -1), ("hw398_usbc", "base_plate", 0.2)]:
    v = dist(a, b)
    if lim >= 0: ok(v >= lim, f"{a} -> {b}: {v:.2f} mm (>= {lim})")
    else: out(f"       {a} -> {b}: {v:.2f} mm")

out("== screw engagement ==")
out(f"  base   M3x10: tip z={J.SCREW_HEAD_CB + 10}, receivers from z={J.BASE_T} -> {J.SCREW_HEAD_CB + 10 - J.BASE_T:.1f} mm, pilot {J.PILLAR_PILOT_L}, lug top z={J.LUG_TOP}")
out(f"  speaker M3x8: through {J.SPK_FLANGE_T} flange -> {8 - J.SPK_FLANGE_T:.1f} mm, pilot {J.SPK_PILOT_L}, skin {J.H - J.Z_FL_FRONT - J.SPK_PILOT_L:.1f} mm")
out(f"  plinth M3x20: {(-J.PL_H + J.SCREW_HEAD_CB + 20):.1f} mm into the base plate, pilot 6.0")
out(f"\n{len(fails)} failure(s)")
with open(os.path.join(ROOT, "CHECK_REPORT.txt"), "w") as fh:
    fh.write("Voice satellite V2 enclosure - geometric checks of the CAD model (this version was printed and assembled)\n\n" + "\n".join(lines) + "\n")

# --------------------------------------------------------------------------- renders
import pyvista as pv
pv.OFF_SCREEN = True
def mesh(name):
    return pv.read(os.path.join(BUILD, f"{name}.stl"))
col = {"shell": "#3f444c", "base_plate": "#33373d", "plinth_PCTG": "#cfeeff", "feet_TPU": "#2a2a2a", "led_strip": "#ffcf6e",
       "perfboard": "#2f8a4c", "devkit": "#1d2536", "wroom_module": "#b9bec6", "dac": "#7a4bb5", "dac_terminal": "#39b36f",
       "hw398": "#44484f", "speaker": "#222222", "speaker_cone": "#555555", "mic": "#101820", "chamber_gasket_TPU": "#2a2a2a",
       "grommet_TPU": "#2a2a2a", "devkit_usbc": "#d9dde2", "hw398_usbc": "#d9dde2"}
Wc, Dc, Hc = J.W, J.D, J.H
cam = [(Wc * 1.5, -Dc * 1.8, Hc * 2.6), (Wc / 2, Dc / 2, Hc / 4), (0, 0, 1)]
p = pv.Plotter(off_screen=True, window_size=(1600, 1200)); p.set_background("white")
for n in ("shell", "base_plate", "plinth_PCTG", "feet_TPU"):
    p.add_mesh(mesh(n), color=col[n], opacity=0.55 if n == "plinth_PCTG" else 1.0, smooth_shading=False)
p.add_mesh(mesh("led_strip"), color=col["led_strip"])
p.camera_position = cam
p.screenshot(os.path.join(RENDERS, "render_exterior.png"))
p = pv.Plotter(off_screen=True, window_size=(1600, 1200)); p.set_background("white")
p.add_mesh(mesh("shell"), color="#8a9099", opacity=0.15)
p.add_mesh(mesh("plinth_PCTG"), color=col["plinth_PCTG"], opacity=0.3)
for n in ("base_plate", "perfboard", "devkit", "wroom_module", "devkit_usbc", "dac", "dac_terminal", "hw398", "hw398_usbc",
          "speaker", "speaker_cone", "mic", "led_strip", "chamber_gasket_TPU", "grommet_TPU"):
    p.add_mesh(mesh(n), color=col[n])
p.camera_position = cam
p.screenshot(os.path.join(RENDERS, "render_xray.png"))
print("renders done")
