# Build notes

These are the key points for rebuilding the V2 satellite (and for anyone attempting V3), written as notes rather than a tutorial. They assume you can solder, read a datasheet and drive a slicer.

![V2 opened like a book](../images/v2-open-case.jpg)
<!-- PHOTO NEEDED: images/v2-open-case.jpg: the V2 case opened like a book (shell upside down next to the base, still joined by the mic and speaker wires), perfboard, speaker and plinth visible; top-down, plain background, no screens or documents in frame. -->

## Electronics (V2)

- **Measure the PD trigger board's output first,** with the charger you'll actually use: 4.75–5.25 V. Anything higher kills the ESP32, the amp and the LEDs.
- **Critical connections:**
  - mic VDD to **3V3** (never 5 V)
  - amp SD to GPIO7 with a 10 kΩ pull-down
  - LED data GPIO14 → 330 Ω → DIN with a 10 kΩ pull-down
  - every module's 5 V / GND straight from the trigger board's pads

  Full table: [hardware/v2](../hardware/v2/README.md).
- **Staged power-up:** don't connect everything at once. Bring it up one part at a time, so a failure points at what you just added:
  1. beep test with no power
  2. bare power with the devkit out
  3. devkit in, check the mic's 3.3 V
  4. amp: SD below 0.08 V with RST held
  5. amp playing
  6. LEDs
  7. full voice run
  8. long answer at full volume with the ring on (no reboot, no brownout in the logs)
- **Finish all soldering and testing before heat-staking** the perfboard to the base plate. Once it's staked, its underside faces the base plate and you can't reach it.
- **Flash over Wi-Fi.** Never connect USB to the devkit while it's on the perfboard (two supplies meet on the 5 V pin).
- **Wire lengths:** the case opens like a book, hinged at the front edge. The mic wires need about 12–15 cm and the speaker wires about 15 cm of slack, which folds into the bay above the electronics.

## Printing (V2)

- **Printer:** Bambu Lab A1 mini, 0.4 mm nozzle, textured PEI plate.
- **Materials:** shell and base plate in black PETG; the light-band plinth in clear PCTG; gaskets, feet and grommet in black TPU.
- **Orientation:** the STLs in [enclosure/v2/stl](../enclosure/v2/stl/) are already in print orientation.
  - The shell prints top face down.
  - No supports are needed anywhere.
  - Use at least 6 walls on the shell so the screw pillars are solid.
- **TPU parts** slowly (20–30 mm/s). Print spare mic rings and a spare grommet; they're tiny.
- **After printing:**
  - poke through the 0.2 mm sacrificial layer in the base plate's counterbores
  - clear the mic port with a 2 mm drill by hand if a skin remains
  - cut one slit from the rim into each wire channel of the grommet
- **Screws straight into PETG:** drive each M3 screw in and out once before assembly to cut the thread. Later, turn it backwards by hand until it clicks into the existing thread, then tighten only snug. The bosses are the hard stops for the gaskets.
- **Check before printing:** an M3 button head next to the round 40 mm speaker body is tight on paper (the head's inner edge reaches r 19.78 mm, the body is r 20). Push a screw through a corner hole from the back of the speaker and see if it sits flat. Mine did, so my shell uses M3. The CAD source has an M2.5 option (`SPK_PILOT_D`) for speakers where it doesn't.

## Assembly order (V2)

1. Perfboard onto the base-plate pins. Heat-stake three of the four pins (flat tip, about 245 °C, Kapton on the tip). The fourth only locates the board.
2. Shell upside down on a towel. Mic into its ring with the TPU port gasket. (This is where my stake pins later failed, see [lessons learned](lessons-learned.md#1-the-heat-staked-mic-pins-broke-under-the-wire-strain).)
3. Speaker: gasket over the four bosses, speaker face down, 4 × M3×8 with a straight 2 mm hex key.
4. Speaker wires through the TPU grommet in the chamber wall. Connect the mic and speaker wires to the perfboard and the amp terminal.
5. Chamber gasket into its groove, a pinch of polyester fibre into the chamber. Lower the shell straight down for the last ~10 mm. Fit 5 × M3×10 from below.
6. LED lead into the plinth, plinth on with 4 × M3×20, feet pressed on over the screw heads.
7. Seal check: press the speaker cone gently. It should push back like an air cushion.

## Things that went wrong

See [lessons learned](lessons-learned.md). In short: the heat-staked mic pins broke, the first answers took a minute, and the V1.2 speaker screws were unreachable.

## If you attempt V3 (unverified)

Read [hardware/v3-pcb/README.md](../hardware/v3-pcb/README.md) first. Nothing about V3 has been built. The parts that will need real-world verification:
- the soldering plan for the TQFN amp (drag-solder the sides, then heat the exposed pad through the 1 mm hole from the back)
- the USB-C overhang against the GCT drawing
- the light-band print settings: for a milky diffuser rather than a see-through window, print the clear band with 1 wall loop, 0 top/bottom layers and 20 % gyroid infill, plus optional fuzzy skin outside
- installing the heat-set inserts (about 260 °C for PCTG)
