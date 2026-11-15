# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Daniel Bernet
"""
Independent read-back of the generated V3 fabrication and KiCad files (rev A, UNVERIFIED design).

Parses the Gerbers and drill files with gerbonara and the KiCad board and schematic with kiutils,
so the files are checked by tools other than the generator that wrote them. Writes read-back
renders of both board sides to ../build/ (git-ignored) for a visual check.

    pip install gerbonara kiutils
    python3 check_outputs.py

Expected for rev A: 9 Gerber layers (bottom paste is empty, there are no bottom SMD parts),
2 drill files, 82 footprints, 74 schematic symbols. This is a parse and look check, not a DFM review.
"""
import os
import sys
import warnings

from gerbonara import ExcellonFile, GerberFile, LayerStack
from kiutils.board import Board
from kiutils.schematic import Schematic

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GERBERS = os.path.join(ROOT, "gerbers")
BUILD = os.path.join(ROOT, "build")
fails = 0

for name in sorted(os.listdir(GERBERS)):
    if name.endswith(".txt"):
        continue
    path = os.path.join(GERBERS, name)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            obj = ExcellonFile.open(path) if name.endswith(".drl") else GerberFile.open(path)
            print(f"OK    {name:28s} objects={len(obj.objects):<5} parser warnings={len(w)}")
        except Exception as e:  # report every file, then fail at the end
            print(f"FAIL  {name}: {e!r}")
            fails += 1

stack = LayerStack.open(GERBERS)
layers = sorted(f"{side} {use}" for side, use in stack.graphic_layers)
drills = list(stack.drill_layers)
print(f"layer stack: {len(layers)} layers ({', '.join(layers)}), {len(drills)} drill files")

board = Board.from_file(os.path.join(ROOT, "kicad", "voice_sat_v3.kicad_pcb"))
sch = Schematic.from_file(os.path.join(ROOT, "kicad", "voice_sat_v3.kicad_sch"))
print(f"kicad_pcb: {len(board.footprints)} footprints, {len(board.nets)} nets (incl. the unnamed net 0)")
print(f"kicad_sch: {len(sch.schematicSymbols)} symbols")

os.makedirs(BUILD, exist_ok=True)
for side in ("top", "bottom"):
    out = os.path.join(BUILD, f"readback_{side}.svg")
    with open(out, "w") as fh:
        fh.write(str(stack.to_pretty_svg(side=side)))
    print(f"render: {os.path.relpath(out, ROOT)}")

if fails or len(layers) != 9 or len(drills) != 2:
    sys.exit(1)
