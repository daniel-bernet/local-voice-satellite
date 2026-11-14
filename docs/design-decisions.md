# Design decisions

Each decision below comes with the reason behind it. Where I actually weighed alternatives, they're listed. Where I didn't, I say so rather than invent a comparison after the fact.

## 1. Local voice assistant instead of a cloud speaker

**Decision:** build a Home Assistant voice satellite with a fully local pipeline.
**Why:** privacy and control. A cloud smart speaker is always listening for a vendor, and its answers depend on that vendor's service. With Home Assistant's Assist pipeline, the wake word, speech-to-text, intents and text-to-speech all run on my own hardware.

## 2. ESP32-S3 (N16R8), INMP441 mic, MAX98357A amp

**Decision:** an ESP32-S3 devkit with 16 MB flash and 8 MB octal PSRAM, an INMP441 I²S MEMS microphone breakout and a MAX98357A I²S amplifier breakout.
**Why:** I picked these myself after web research. They met my requirements and were readily available on AliExpress. **I didn't seriously compare alternatives.** In hindsight they turned out to be a good fit:
- micro_wake_word needs PSRAM, and the N16R8 has 8 MB of octal PSRAM. The firmware enables it explicitly.
- Both audio parts are digital I²S devices that ESPHome supports directly. The microphone delivers digital samples and the amp takes digital audio, so there's no analog audio wiring on the perfboard.
- The ESP32-S3 has two I²S controllers, so the mic (bus 0) and the amp (bus 1) run independently.

**Later note:** the INMP441 is end of life. The V3 design treats the ICS-43434 as its replacement on the same carrier footprint.

## 3. Wake word on the device

**Decision:** micro_wake_word with the `hey_jarvis` model, running on the ESP32-S3.
**Why:** the satellite streams audio only after the wake word, so nothing leaves the device while it's idle, and the server doesn't have to process a constant audio stream. The LED ring starts reacting at the same moment, which makes it feel responsive.

## 4. Local speech-to-text and text-to-speech

**Decision:** Whisper for speech-to-text and Piper for text-to-speech, both connected to Home Assistant through the Wyoming protocol. Speech-to-text runs on the CPU.
**Why:** both run locally with no cloud account. **Alternative considered:** Whisper used to run on the server's GPU. I moved it to the CPU so the GPU stays free for the planned local LLM. That change was made *before* the latency measurements in [lessons learned](lessons-learned.md#2-the-first-answers-took-about-a-minute), so it doesn't explain the later improvement.

## 5. Amplifier power gating

**Decision:** the amp's SD (shutdown) pin is driven by GPIO7, with a 10 kΩ pull-down. The firmware switches the amp on when playback starts and off 400 ms after it ends.
**Alternative (previous build):** SD tied to VCC, so the amp was always on.
**Why:** with the amp permanently on, the speaker hissed and crackled between answers. Gating it fixed that. The pull-down keeps the amp off while the ESP32 boots. All audio goes through one media player, so there's exactly one place in the firmware that switches the amp.

## 6. LED strip driven at 3.3 V without a level shifter (V2)

**Decision:** GPIO14 → 330 Ω → strip data input, plus a 10 kΩ pull-down, with no level shifter.
**Alternative considered:** a 74AHCT125 buffer to lift the data signal to 5 V logic.
**Why:** I didn't have the chip on hand. Newer WS2812B (V5) accept 3.3 V data on a 5 V supply (threshold 0.63 × VDD ≈ 3.15 V). Older parts specify 0.7 × VDD and usually work anyway. I kept room on the perfboard for the buffer in a DIP socket as a fallback. The 330 Ω damps ringing, and the pull-down keeps the strip dark during boot. The LED tests before closing the case passed, and the satellite runs without the buffer. V3 includes a single-gate buffer (74AHCT1G125) anyway, because a PCB makes it nearly free.

## 7. Power: USB-C at 5 V with a star point

**Decision (V2):** a USB-C PD trigger board set to 5 V. Every module gets its own 5 V / GND pair straight from the board's output pads. A 470 µF capacitor sits at the amp and a 1000 µF capacitor at the LED strip input.
**Why:** the LED and amp current never flows through the devkit's pins, and the bulk capacitors cover the amp's peaks and protect the first LED at switch-on. The LED brightness is capped in firmware (60 %) to stay within the 5 V / 3 A budget.
**V3:** no trigger board. 5.1 kΩ pull-downs on the USB-C CC pins request 5 V from any USB-C source. The ESP32 reads the CC voltage to see how much current the charger advertises (default, 1.5 A or 3 A) and caps the LEDs accordingly. A PTC fuse, a TVS diode and USB ESD protection are on the board.

## 8. Case concept

**Decision:** a compact box with:
- a **sealed speaker chamber**, the speaker firing **upwards** through a hex grille
- the **mic on the front wall**, at 90° to the speaker and about 61 mm from it
- an **LED light band** below the case: a clear PCTG plinth in V2, a clear band in the wall in V3
- **no visible screws**: the plinth or the feet cover them

**Why, and how it got there:** the speaker originally sat inside the chamber. In V1.2 its screws turned out to be unreachable behind the speaker body and the boss columns, so V2 mounts the speaker on top, screwed in from inside with the shell upside down, where a straight hex key reaches every screw. The sealed chamber with TPU gaskets gives the small driver a defined back volume. The mic faces a different direction from the speaker to reduce coupling. The light band makes the pipeline state visible from across the room without being harsh.

## 9. Screws straight into PETG (V2)

**Decision:** M3 button-head screws threaded straight into 2.6 mm printed pilot holes, with no heat-set inserts.
**Why:**
- I had no heat-set inserts on hand when V2 was designed.
- In an earlier iteration, inserts would have had to be pressed in sideways deep inside the chamber, which you can't do with a soldering iron.

Self-tapping into PETG works if you cut the thread once and then go easy: drive each screw in and out once before assembly, re-start by hand by turning backwards until it clicks into the existing thread, and tighten only snug.
**V3:** once I had inserts, the V3 case uses heat-set inserts for every screw, and the check script verifies that the iron can reach each insert straight on.

## 10. A custom PCB for V3

**Decision:** design a custom main board.
**Alternative:** keep building on perfboard.
**Why:** the gains are mechanical and electrical, not acoustic: no perfboard and 20+ hand-run wires, LEDs on the board, a flush USB-C port, ESD protection, a fuse and a level shifter, and repeatable builds. The mic, speaker and amp stay in the same class, because the limits are the 40 mm driver and the room, not the parts.

**Sub-decisions:**
- **Hand-solderable only.** I only have an iron, so the board uses 0805/SOT/5050 parts. The single fine-pitch IC (the MAX98357A in TQFN) and the ESP32 module's exposed pad get back-solder holes.
  - **Alternative considered:** an optional footprint for an amp module as a fallback. It made the board unroutable, so it was dropped.
- **Mic stays a module.** Bottom-port MEMS microphones need reflow soldering, so the mic module sits on a small breakaway carrier PCB that screws to the front wall.
  - **Alternative considered:** cutting the carrier from a generic double-sided prototype board, which is documented as a fallback in case the fab charges extra for the breakaway.
- **Speaker wires solder to pads inside the sealed chamber.**
  - **Alternative considered:** a JST connector on the board and a TPU grommet through the chamber wall (the V2 approach). The pads remove the connector and the hole, which helps the seal.
- **Antenna over a different edge from the USB-C port.** The USB-C receptacle must sit flush with the back wall, while the antenna needs air around it. Putting both on one edge didn't work.

## 11. Designing hardware as code

**Decision:** the case is parametric build123d code. The V3 PCB is generated by a Python toolkit (`pcbkit.py`) that places parts, routes them, fills zones, runs a geometric DRC and writes a KiCad 9 project plus Gerbers.
**Why:** every change is a diff, and the checks (collisions, gasket coverage, assembly paths, tool access, DRC, connectivity) re-run on every change. It also suited working with an AI assistant, which can write and check code but has no CAD or KiCad GUI. The generated KiCad project is meant to be opened, checked and finished in KiCad before anything is ordered. See [how it was built](how-it-was-built.md).
