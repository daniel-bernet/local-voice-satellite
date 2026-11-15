# Lessons learned

These are honest and specific: what went wrong, what I changed, and what is still open.

## 1. The heat-staked mic pins broke under the wire strain

**What happened:** in the V2 case, the round INMP441 board sits in a ring on the inside of the front wall. Two printed pins pass through the board's edge notches and are melted over (heat-staked) to hold it. Six wires leave the mic board and run to the perfboard. The melted-down plastic pins didn't take the force of those wire connections and broke off, and I had to glue the mic in.

![V2 mic in the front-wall ring](../images/v2-mic-mount.jpg)
<!-- PHOTO NEEDED: images/v2-mic-mount.jpg: close-up of the mic board in the front-wall ring of the open V2 shell, showing the broken stake pins and the glue; shell upside down, lit from the side, only the device in frame. -->

**What I changed (V3 design):** the mic module solders onto a small **carrier PCB**. The carrier is delivered as a breakaway on the same panel as the main board, and it screws into two heat-set inserts on the front wall. A JST-PH pigtail connects it to the main board, so the wire forces land on a screwed PCB and a connector instead of on two thin plastic pins.

**Lesson:** a heat-staked plastic pin can position a part, but it shouldn't carry load. Anything with several wires attached needs a mechanical fixing that's stronger than the wires.

## 2. The first answers took about a minute

**What happened:** right after assembly, a simple question like "what time is it" took about **1 min** end to end. The LED ring narrows it down roughly: a long "breathing" phase means end of speech wasn't detected, and a long "comet" phase means speech-to-text or the answer is slow.

**Where it is now:** simple requests (time, weather) take about **5–10 s** end to end. I haven't measured the individual stages, so I don't know which change made the difference, and I'm not going to guess.

**Open to-do:** measure the stage times (end-of-speech detection, STT, intent, TTS) in the Assist pipeline's debug view before optimising anything further.

**Lesson:** measure per stage before changing things. "It's slow" isn't a diagnosis.

## 3. Driving the LED strip without a level shifter

**What happened:** I didn't have a 74AHCT125 on hand, so the WS2812B strip's data line is driven straight from a 3.3 V GPIO through 330 Ω, with a 10 kΩ pull-down. On paper that's marginal: newer WS2812B accept 3.3 V on a 5 V supply, while older ones specify 3.5 V. The pre-assembly tests passed with no flicker and no random pixels, and it runs that way.

**What I kept in reserve:** free space on the perfboard for the buffer in a DIP socket, with the firmware unchanged, because the buffer doesn't invert the signal. Retrofitting it would mean opening the case.

**Lesson:** "it works on the bench" is good enough for a one-off, but it isn't a margin. The V3 board includes a single-gate buffer (74AHCT1G125), because on a PCB it costs almost nothing.

## 4. Smaller lessons from the iterations

- **V1.2 speaker screws were unreachable.** The speaker sat inside the chamber, and its screws ended up behind the speaker body and the boss columns. V2 moved the speaker to the top, mounted from inside with the shell upside down, and the CAD checks now verify that a straight hex key reaches every screw.
- **The shell couldn't be closed (caught in CAD).** An early version had a closed USB-C cutout: lowering the shell would have hit the connector. A simulated "lower the shell" sweep in the check script found it before printing. The cutout is now a notch, closed by a tongue on the base plate.
- **Speaker hiss between answers.** This was fixed by amp power gating (see [design decisions](design-decisions.md#5-amplifier-power-gating)), not by changing parts.
- **ESPHome build failure.** The first build on a new ESPHome version failed in the ESP-IDF bootloader sub-build (a missing ninja path). It was a build-environment issue, not the config. "Clean build files" and a rebuild fixed it.
- **Generated outputs need an independent check.** While preparing this repo, reading the generated Gerbers back with a separate tool showed silkscreen text missing inside the speaker-chamber outline. The Gerber writer emitted a large outline whose "clear" hole erased text written before it. The generator now writes outer shapes first. The board's own checks couldn't have caught this, because the board model was fine and only the file output was wrong.
- **Estimated vs measured.** The CAD marks every dimension as *MEASURED* or *EST*. The estimates (amp board position, speaker magnet size) are exactly where a test print matters, and it took two test prints to get to V2.

## What I'd do differently

- Design the mic fixing for the wire forces from the start.
- Set up the pipeline's stage-time measurement before judging latency.
- Buy the level shifter and heat-set inserts *before* designing around their absence.
- Keep the generated fabrication files under the same scrutiny as the design itself: read them back, render them, look at them.
