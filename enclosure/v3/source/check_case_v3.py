# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Daniel Bernet
"""Verification suite for case_v3 (collisions, keep-outs, seal, assembly, printability) + renders.
Run case_v3.py first (it writes ../build and ../stl). Writes ../CHECK_REPORT.txt and ../renders/*.png.
These are geometric checks of the CAD model; the V3 enclosure has never been printed."""
import os, sys, math, itertools, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import case_v3 as J
from build123d import *

comps, case = J.build()
allp = {**{k: v[0] for k, v in comps.items()}, **{k: v[0] for k, v in case.items()}}
BUILD = os.path.join(J.ROOT, "build")
STL = os.path.join(J.ROOT, "stl")
RENDERS = os.path.join(J.ROOT, "renders")
os.makedirs(BUILD, exist_ok=True); os.makedirs(RENDERS, exist_ok=True)
report = []

# 1. integrity
for name, (shape, _) in case.items():
    n = len(shape.solids())
    report.append(f"[integrity] {name}: {n} solid(s), valid={shape.is_valid}")
    if name not in ("feet_TPU",) and n != 1:
        report.append(f"   !! {name} has {n} solids")

# 2. collision matrix (printed parts vs components, pairs of printed parts)
EXPECTED = [{"chamber_gasket_TPU", "shell_black"}, {"chamber_gasket_TPU", "pcb"}, {"speaker_gasket_TPU", "speaker"},
            {"speaker_gasket_TPU", "shell_black"}, {"mic_gasket_TPU", "shell_black"}, {"mic_gasket_TPU", "mic"},
            {"feet_TPU", "base_plate"}, {"shell_black", "shell_band_clear"},
            {"speaker_cone", "speaker"}, {"spk_screw_heads", "speaker"}, {"spk_key_paths", "spk_screw_heads"},
            {"leds", "pcb_parts"}, {"pcb_bottom_solder_keepout", "pcb"}, {"spk_cable_keepout", "spk_screw_heads"},
            {"spk_cable_keepout", "spk_key_paths"}, {"mic_header", "mic"}, {"mic_header", "mic_carrier"}, {"mic_screw_heads", "mic_carrier"}, {"mic_solder_keepout", "mic_carrier"}, {"mic_solder_keepout", "mic_screw_heads"}, {"mic_jst_keepout", "mic_carrier"}, {"mic_jst_keepout", "mic_solder_keepout"}, {"mic_carrier", "shell_black"},
            {"usb_plug_keepout", "usbc"}, {"spk_cable_keepout", "speaker"}, {"chamber_gasket_TPU", "shell_band_clear"},
            {"pcb_bottom_solder_keepout", "base_plate"}, {"speaker", "shell_black"}, {"mic", "shell_black"}, {"pcb", "shell_black"}, {"pcb", "base_plate"}]
names = list(allp)
coll = []
for a, b in itertools.combinations(names, 2):
    if {a, b} in EXPECTED:
        continue
    if "keepout" in a and "keepout" in b:
        continue
    v = J.vol(allp[a], allp[b])
    if v > 0.05:
        coll.append((a, b, round(v, 2)))
        if a == "pcb_parts" or b == "pcb_parts":
            other = allp[b if a == "pcb_parts" else a]
            for p in J.BRD["parts"]:
                x0, y0, x1, y1 = p["bounds"]
                bx = J.box(J.OX + x0, J.OX + x1, J.OY + y0, J.OY + y1, J.Z_PCB1, J.Z_PCB1 + max(p["height"], 0.6))
                if J.vol(bx, other) > 0.01:
                    report.append(f"   part {p['ref']} overlaps {b if a == 'pcb_parts' else a} by {J.vol(bx, other):.2f} mm3")
report.append(f"[collisions] unexpected overlaps: {coll}")

# 3. keep-out margins (components/keep-outs vs printed parts)
printed = [k for k in case]
for ko in [k for k in allp if "keepout" in k or k in ("usbc", "esp32_module", "pcb_parts", "leds", "speaker", "mic")]:
    for p in printed:
        if {ko, p} in EXPECTED:
            continue
        d = allp[ko].distance_to(allp[p])
        if d < 0.3:
            report.append(f"[keepout] {ko} <-> {p}: {d:.2f} mm {'!!' if d < 0.05 else '(must-measure)'}")

# 4. seal: gasket rib fully under the chamber rim, groove fill
gk = allp["chamber_gasket_TPU"]
rim = J.rr_offset(J.CHAMBER_CL, J.CH_WALL / 2, J.Z_PCB1 - 0.2, J.Z_PCB1) - J.rr_offset(J.CHAMBER_CL, -J.CH_WALL / 2, J.Z_PCB1 - 1, J.Z_PCB1 + 1)
groove = J.rr_band(J.CHAMBER_CL, -J.GROOVE_W / 2, J.GROOVE_W / 2, J.Z_PCB1, J.Z_PCB1 + J.GROOVE_D)
base_in_groove = J.vol(gk, groove)
report.append(f"[seal] gasket volume {gk.volume:.1f} mm3, groove volume {groove.volume:.1f}, fill {base_in_groove / groove.volume * 100:.0f} % (target 75-85)")
proud = J.vol(gk, J.box(-1, J.W + 1, -1, J.D + 1, J.Z_PCB1 - 5, J.Z_PCB1))
report.append(f"[seal] rib proud below the rim face: {proud:.1f} mm3 ({J.GK_BASE_H + J.GK_RIB_H - J.GROOVE_D:.2f} mm proud -> squeezed to the hard stop on the PCB)")
rim_pcb = J.vol(rim, allp["pcb"])
report.append(f"[seal] rim footprint on the PCB: {rim_pcb / rim.volume * 100:.0f} % of the rim sits over the PCB (want 100)")
for (x, y) in J.HOLES:
    d = J.cyl_z(x, y, J.Z_PCB1, J.Z_PCB1 + 8, 2.6).distance_to(groove)
    report.append(f"[seal] corner screw hole at ({x:.1f},{y:.1f}) to groove: {d:.2f} mm (>=1.5)")

# 5. assembly path: shell lowered over base+PCB+parts (sweep the real solids)
shell = allp["shell_black"] + allp["shell_band_clear"]
mating = allp["pcb"] + allp["usbc"] + allp["pcb_parts"] + allp["esp32_module"] + allp["base_plate"] + allp["leds"]
blocked = 0.0
for k in range(0, 60):
    dz = 0.5 * k
    v = J.vol(Pos(0, 0, dz) * shell, mating)
    if v > 0.05:
        blocked = max(blocked, v)
report.append(f"[assembly] shell sweep over base/PCB/parts: max overlap {blocked:.2f} mm3 (0 = free path)")
spk = allp["speaker"]
blk = max(J.vol(Pos(0, 0, -0.5 * k) * spk, allp["shell_black"]) for k in range(1, 70))
report.append(f"[assembly] speaker drop-in path through the chamber: max overlap {blk:.2f} mm3")

# 6. tool access: screwdriver from below for the 4 base screws
for (x, y) in J.HOLES:
    path = J.cyl_z(x, y, -40, J.SCREW_HEAD_CB, 3.0)
    for p in ("pcb", "pcb_parts"):
        d = path.distance_to(allp[p])
        if d < 0.3:
            report.append(f"[tool] base screw ({x:.1f},{y:.1f}) driver path blocked by {p}: {d:.2f}")

# 6b. insert iron paths: mic bosses (iron tip cylinder 6 mm along -y from the bay), speaker bosses (from inside the chamber, along -z)
for sx in (-1, 1):
    path = J.cyl_y(J.MIC_X + sx * J.CAR_HOLE_DX, J.MIC_Z, J.Y_CARRIER0 + 0.2, J.Y_CARRIER0 + 40, 6.0)
    d = path.distance_to(allp["shell_black"])
    report.append(f"[tool] iron to mic insert {sx}: clearance to shell {d:.2f} mm")
for (sx, sy) in J.SPK_SCREWS:
    path = J.cyl_z(sx, sy, J.Z_PCB1 + 2, J.Z_FL_FRONT - 0.2, 6.0)
    d = path.distance_to(allp["shell_black"])
    report.append(f"[tool] iron to speaker insert ({sx:.0f},{sy:.0f}): clearance {d:.2f} mm")

# 7. printability per print pose (downward faces above the first layer)
import trimesh
for name in case:
    f = os.path.join(STL, f"{name}.stl")
    if not os.path.exists(f):
        continue
    m = trimesh.load(f)
    n = m.face_normals; c = m.triangles_center; z0 = m.bounds[0][2]
    idx = np.where((n[:, 2] < -0.72) & (c[:, 2] > z0 + 0.3))[0]
    flagged = []
    if len(idx):
        sub = m.submesh([idx], append=True)
        for comp in sub.split(only_watertight=False):
            e = comp.bounds[1] - comp.bounds[0]
            short = min(e[0], e[1])
            if short > 8.0:
                flagged.append((round(short, 1), round(float(comp.bounds[0][2]), 1), [round(v, 1) for v in comp.bounds[0][:2]]))
    report.append(f"[print] {name}: watertight={m.is_watertight}, flagged overhang clusters (short span > 8 mm): {flagged[:6]}")

# 8. volumes / numbers
inner = J.rr_offset(J.CHAMBER_CL, -J.CH_WALL / 2, J.Z_PCB1, J.Z_CEIL)
report.append(f"[acoustics] chamber gross volume {inner.volume / 1000:.0f} cm3, minus speaker {(inner.volume - allp['speaker'].volume) / 1000:.0f} cm3")
report.append(f"[size] case {J.W} x {J.D} x {J.H} mm (+3 mm feet); V2 was 111.2 x 85.6 x 51.4 + plinth/feet")

with open(os.path.join(J.ROOT, "CHECK_REPORT.txt"), "w") as fh:
    fh.write("Voice satellite V3 enclosure - geometric checks of the CAD model (never printed)\n\n" + "\n".join(report) + "\n")
print("\n".join(report))

# --------------------------------------------------------------------------- renders
import pyvista as pv
pv.OFF_SCREEN = True
def mesh(name):
    return pv.read(os.path.join(BUILD, f"{name}.stl"))
light = {"shell_black": "#8a9099", "shell_band_clear": "#9fd8ff", "base_plate": "#6f757d", "chamber_gasket_TPU": "#e8873a",
         "speaker_gasket_TPU": "#e8873a", "mic_gasket_TPU": "#e8873a", "feet_TPU": "#e8873a",
         "pcb": "#2f8a4c", "pcb_parts": "#c9ced6", "esp32_module": "#dfe3e8", "usbc": "#f0f0f0", "speaker": "#222222", "speaker_cone": "#555555",
         "mic": "#101820", "leds": "#ffe066", "mic_carrier": "#2f8a4c"}
Wc, Dc, Hc = J.W, J.D, J.H
# a) exterior overview
p = pv.Plotter(off_screen=True, window_size=(1600, 1200)); p.set_background("white")
for n in ("shell_black", "shell_band_clear", "base_plate", "feet_TPU"):
    p.add_mesh(mesh(n), color=light[n], opacity=1.0 if n != "shell_band_clear" else 0.6)
p.camera_position = [(Wc * 1.5, -Dc * 1.8, Hc * 2.2), (Wc / 2, Dc / 2, Hc / 2), (0, 0, 1)]
p.screenshot(os.path.join(RENDERS, "render_exterior.png"))
# b) x-ray overview
p = pv.Plotter(off_screen=True, window_size=(1600, 1200)); p.set_background("white")
p.add_mesh(mesh("shell_black"), color=light["shell_black"], opacity=0.15)
p.add_mesh(mesh("shell_band_clear"), color=light["shell_band_clear"], opacity=0.25)
for n in ("base_plate", "pcb", "pcb_parts", "esp32_module", "usbc", "speaker", "speaker_cone", "mic", "mic_carrier", "leds", "chamber_gasket_TPU"):
    p.add_mesh(mesh(n), color=light[n])
p.camera_position = [(Wc * 1.5, -Dc * 1.8, Hc * 2.2), (Wc / 2, Dc / 2, Hc / 2), (0, 0, 1)]
p.screenshot(os.path.join(RENDERS, "render_xray.png"))
# c) section through the chamber and the LED band (y = speaker centre)
cutbox = J.box(-5, Wc + 5, J.SPK_CY, Dc + 5, -10, Hc + 10)
p = pv.Plotter(off_screen=True, window_size=(1600, 1000)); p.set_background("white")
for n in ("shell_black", "shell_band_clear", "base_plate", "pcb", "pcb_parts", "speaker", "chamber_gasket_TPU", "leds", "feet_TPU"):
    s = allp[n] - cutbox
    if s is None or s.volume < 0.01:
        continue
    export_stl(s, os.path.join(BUILD, f"_sec_{n}.stl"), tolerance=0.05, angular_tolerance=0.2)
    p.add_mesh(pv.read(os.path.join(BUILD, f"_sec_{n}.stl")), color=light[n])
p.camera_position = [(Wc / 2, Dc * 3, Hc / 2), (Wc / 2, Dc / 2, Hc / 2), (0, 0, 1)]
p.enable_parallel_projection(); p.camera.parallel_scale = Hc * 0.75
p.screenshot(os.path.join(RENDERS, "render_section_y.png"))
print("renders done")
