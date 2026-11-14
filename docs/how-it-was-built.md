# How it was built

The hardware design files in this repository were produced **as code, with AI assistance**. I want to be plain about who did what, because "AI-designed" can mean anything from "I typed one prompt" to "I used autocomplete".

## What I did

- **Defined the project:** a private, local voice satellite for Home Assistant, plus its requirements and constraints (printer, materials, parts on hand, no visible screws, hand-soldering only).
- **Chose the core components** (ESP32-S3 N16R8, INMP441, MAX98357A, speaker, LED strip, USB-C PD trigger) after my own web research, and ordered them.
- **Measured the real parts.** Every dimension marked *MEASURED* in the CAD source came from me. The *EST* values are estimates from photos.
- **Reviewed every iteration** and made the calls: millimetre adjustments, rejected options, choices between trade-offs (for example: driving the LEDs without a level shifter, the mic carrier PCB after the stake pins broke, solder pads instead of a speaker connector).
- **Printed** every part on my Bambu Lab A1 mini, including the test prints that found the unreachable V1.2 speaker screws.
- **Soldered, assembled and tested** the V2 electronics, following a staged power-up test plan.
- **Set up** ESPHome and the Home Assistant voice pipeline, and flashed and run the firmware.

## What was generated with AI assistance (Claude, by Anthropic)

- **Enclosure CAD:** the build123d source for the V2 and V3 cases and their check scripts (collisions, gasket coverage, assembly sweeps, tool access, printability).
- **V3 PCB:** the `pcbkit.py` toolkit (footprints from datasheet numbers, an A* grid router, zone fills, a geometric DRC, KiCad 9 and Gerber writers) and the board script. There was no KiCad in the AI's environment, so the board is generated as files that KiCad opens. It has **not** been opened, checked or fabricated in KiCad yet.
- **Firmware:** the current ESPHome configuration, including the amp power gating and the LED state machine, was written with AI assistance and then validated and flashed by me. The V3 config is an AI-written draft.
- **Documentation:** the wiring and soldering guides I built from, the wiring diagram (SVG written as code) and these docs, drafted from my project notes and reviewed by me.
- **This repository's generated outputs** (KiCad project, Gerbers, BOM, STL/STEP, renders) were regenerated from the source while the repo was prepared.

## What the automated checks do and don't prove

| Check | Proves | Doesn't prove |
|---|---|---|
| Case collision, seal and assembly checks | The CAD parts don't intersect, the gaskets sit where they should, the parts can be assembled in the modelled order | That *estimated* dimensions match the real parts, or that it prints well. Only a test print shows that. |
| PCB geometric DRC + connectivity | The generated board model meets the clearance rules it was given and every net is connected | That the footprints match the real parts (they're datasheet re-creations), or that the circuit works. KiCad's own DRC has not been run. |
| Gerber read-back + render | The files parse in an independent tool and look like the board | That a fab will accept them without questions |
| `esphome config` | The YAML is a valid configuration for the ESPHome version used | That it runs correctly on hardware. For V3 there is no hardware. |

The V2 satellite is the only part that has been proven by building it.
