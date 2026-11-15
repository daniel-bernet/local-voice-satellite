# How it was built

This project was built with AI assistance (Claude, by Anthropic). I want to be plain about who did what, because "AI-assisted" can mean anything from "I typed one prompt" to "I used autocomplete".

In short: I defined the requirements, chose the components, specified and reviewed the designs, and printed, soldered, assembled and tested the hardware. The PCB and the case were generated as code, and the firmware, the guides, the wiring diagram and the doc drafts were written with AI support. I reviewed, adapted and tested all of it, with my own input at every step.

## What I did

- **Defined the project:** a private, local voice satellite for Home Assistant, plus its requirements and constraints (printer, materials, parts on hand, no visible screws, hand-soldering only).
- **Chose the core components** (ESP32-S3 N16R8, INMP441, MAX98357A, speaker, LED strip, USB-C PD trigger) after my own web research, and ordered them.
- **Measured the real parts.** Every dimension marked *MEASURED* in the CAD source came from me. The *EST* values are estimates from photos.
- **Specified and reviewed every design iteration** and made the calls: millimetre adjustments, rejected options, choices between trade-offs (for example: driving the LEDs without a level shifter, the mic carrier PCB after the stake pins broke, solder pads instead of a speaker connector).
- **Printed** every part on my Bambu Lab A1 mini, including the test prints that found the unreachable V1.2 speaker screws.
- **Soldered, assembled and tested** the V2 electronics, following a staged power-up test plan.
- **Set up** ESPHome and the Home Assistant voice pipeline, and flashed, ran and adjusted the firmware.

## What was written with AI assistance, then reviewed, adapted and tested by me

- **Enclosure CAD:** the build123d source for the V2 and V3 cases and their check scripts (collisions, gasket coverage, assembly sweeps, tool access, printability). The V2 case was printed and assembled; the V3 case has not been printed.
- **V3 PCB:** the `pcbkit.py` toolkit (footprints from datasheet numbers, an A* grid router, zone fills, a geometric DRC, KiCad 9 and Gerber writers) and the board script. There was no KiCad in the AI's environment, so the board is generated as files that KiCad opens. It has **not** been opened, checked or fabricated in KiCad yet.
- **Firmware:** the ESPHome configuration, including the amp power gating and the LED state machine. I validated, flashed and tested the V2 config on the satellite. The V3 config is a draft and has never run, because the board doesn't exist.
- **Guides and diagram:** the wiring and soldering guides I built V2 from, and the wiring diagram (an SVG written as code).
- **Documentation:** these docs, drafted from my project notes and reviewed and corrected by me.
- **This repository's generated outputs** (KiCad project, Gerbers, BOM, STL/STEP, renders) were regenerated from the source while the repo was prepared.

## What the automated checks do and don't prove

| Check | Proves | Doesn't prove |
|---|---|---|
| Case collision, seal and assembly checks | The CAD parts don't intersect, the gaskets sit where they should, the parts can be assembled in the modelled order | That *estimated* dimensions match the real parts, or that it prints well. Only a test print shows that. |
| PCB geometric DRC + connectivity | The generated board model meets the clearance rules it was given and every net is connected | That the footprints match the real parts (they're datasheet re-creations), or that the circuit works. KiCad's own DRC has not been run. |
| Gerber read-back + render | The files parse in an independent tool and look like the board | That a fab will accept them without questions |
| `esphome config` | The YAML is a valid configuration for the ESPHome version used | That it runs correctly on hardware. For V3 there is no hardware. |

The V2 satellite is the only part that has been proven by building it.
