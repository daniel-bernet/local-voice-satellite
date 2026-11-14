# ESPHome configs

| File | For | Status |
|---|---|---|
| [voice-satellite-v2.example.yaml](voice-satellite-v2.example.yaml) | Satellite V2 (hand-wired) | Sanitised copy of the config running on the V2 satellite |
| [voice-satellite-v3.example.yaml](voice-satellite-v3.example.yaml) | Satellite V3 (custom PCB, rev A) | **Draft, never flashed.** The board doesn't exist. |
| [secrets.example.yaml](secrets.example.yaml) | both | Copy it to `secrets.yaml` and fill in your values |

Both configs pass `esphome config` with ESPHome 2026.10.2. That's a schema check, not a compile or a hardware test. The only warning is that ESPHome now recommends OTA `encryption` instead of an OTA `password`. The wake-word model `hey_jarvis` is fetched by ESPHome from [esphome/micro-wake-word-models](https://github.com/esphome/micro-wake-word-models) at build time.

**Use:** in the ESPHome Device Builder, create a device, paste the YAML and add the four secrets. Generate a separate API encryption key per device; Home Assistant asks for it when you adopt the device. Flash the first time over USB, after that over Wi-Fi. On V2, never connect USB to the devkit while it sits on the perfboard (see [docs/wiring.md](../../docs/wiring.md)).

**What the config does:** I²S mic and amp on separate buses, on-device wake word, amp power gating through the shutdown pin, and an LED ring state machine with per-stage timeouts. The design reasons are in [docs/architecture.md](../../docs/architecture.md) and [docs/design-decisions.md](../../docs/design-decisions.md).
