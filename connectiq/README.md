# HR Thresholds — Connect IQ data field

The on-bike half of this skill. It runs the same zone model as
`scripts/calculate_hr_zones.py`, the same best-window rules as
`scripts/analyze_field_hr.py` and the same steady-climb physics as
`climb_power()` in `scripts/estimate_ftp_without_power_meter.py` live on a
Garmin Edge, so every ride records the evidence the desktop analysis looks for.
Everything on the device is deterministic arithmetic; the judgement calls
(which efforts count, what the thresholds are) stay with the skill.

| On screen | Saved to the FIT session |
|---|---|
| Current HR + Z1–Z5 badge (dual-threshold model) | Best 20 / 30 / 40 / 60 min HR |
| Time below VT1 / VT1–LTHR / at or above LTHR | % time in each of the three domains |
| Best 20–60 min HR and its gap to LTHR | |
| Climb virtual power, low–high range (live and best climb) | Best climb power (base, low, high), duration, grade |

The layout adapts to the field size: one-line, half-page and full-page.

## Behaviour that matches the Python helpers

- Zones: `Z2 = floor(0.9·VT1)+1`, `Z3 = VT1`, `Z4 = floor(0.9·LTHR)+1`,
  `Z5 = LTHR`. Anchors that empty a zone are rejected, exactly like
  `build_zones()`.
- Best windows: 1 Hz runs, gaps up to `MaxGap` seconds (default 12, the
  `--max-interpolation-gap-seconds` default) are linearly interpolated, longer
  gaps or paused timer end the run. HR outside 25–260 bpm is discarded.
- Thresholds are never inferred. With VT1/LTHR unset the field colours by the
  rider's Garmin cycling zones and shows a setup prompt instead of domains.

## Climb virtual power

No heart rate is involved. On a steady climb the field estimates crank power
from physics, exactly as `climb_power()` does:

`P = v × (m g sin θ + m g Crr cos θ + ½ ρ CdA v_air |v_air|) / efficiency`

- **Detection:** a climb starts when the trailing 60 s grade reaches 4 % and
  ends when it drops below 2 %, the rider falls 15 m below the summit, covers
  under 30 m in 60 s (a stop with auto-pause off), pauses, or loses samples
  for longer than `MaxGap`. It runs from the last low point before the climb to
  the first time it reached its summit. Climbs under 10 min are not kept.
- **Inputs:** distance, barometric altitude, rider mass (setting, else the
  Garmin profile; with neither the feature stays off), bike mass, CdA, Crr,
  drivetrain efficiency, and air density from barometric pressure and the
  temperature setting (mean of the start and summit values).
- **Range, always shown:** low/high scenarios move every uncertain input the
  same way: CdA ±0.04 m², Crr ±0.001, efficiency ∓1.5 pts, 2 m/s tail/headwind,
  mass ±1 kg, elevation gain ±3 %. When space is short the screen shows the
  range (`228-262 W`), never the base value alone.
- **Not modelled:** drafting, acceleration, braking, cornering, wind beyond the
  ±2 m/s scenario. Ride climbs solo and steadily for usable numbers.
- **FTP candidate, not FTP.** A 40–70 min climb is labelled `FTP?`
  (`FTP候选` in Chinese), for example `Best 52' 6.1% FTP?  228-262 W`. That is
  the only duration the skill accepts as an FTP proxy, and only if the effort
  was maximal, steady and solo, which the device cannot judge, so the label
  stays a question.
- **Power meter:** if one covers ≥90 % of the climb, the screen shows its
  reading (`PM 240 W`) instead; the FIT fields keep the modelled values so the
  two can be compared afterwards.

## Settings (Garmin Connect → device → Connect IQ → HR Thresholds)

| Key | Meaning | Default |
|---|---|---|
| `VT1` | VT1/GET heart rate, bpm | 0 (unset) |
| `LTHR` | Cycling LTHR/LT2, bpm | 0 (unset) |
| `MaxGap` | Longest HR/sample gap to bridge, seconds | 12 |
| `RiderKg` | Rider mass, kg (0 = Garmin profile weight) | 0 |
| `BikeKg` | Bike + kit mass, kg | 9 |
| `CdA` | Drag area in climbing position, m² | 0.32 |
| `Crr` | Rolling resistance coefficient | 0.005 |
| `Efficiency` | Drivetrain efficiency | 0.975 |
| `TempC` | Air temperature for density, °C | 20 |

## Build

Install the [Connect IQ SDK](https://developer.garmin.com/connect-iq/sdk/) and,
through SDK Manager, the device files for the products in `manifest.xml`. Then:

```bash
export CIQ_SDK=~/connectiq-sdk/sdk CIQ_KEY=~/connectiq-sdk/developer_key.der
./build.sh            # debug build for edge540 (DEVICE=edge1040 ./build.sh for others)
./build.sh test       # unit tests in the simulator
./build.sh package    # bin/HrThresholds.iq for the Connect IQ Store
```

Generate a developer key once with:

```bash
openssl genrsa -out developer_key.pem 4096
openssl pkcs8 -topk8 -inform PEM -outform DER -in developer_key.pem -out developer_key.der -nocrypt
```

Keep the key private and backed up: store updates must be signed with the same
key. Never commit it (`*.der` and `*.pem` are ignored).

## Sideload without the store

Copy `bin/HrThresholds-edge540.prg` to `GARMIN/APPS/` on the Edge over USB,
then add the field to a data screen.

## Publish

Upload `bin/HrThresholds.iq` at <https://apps.garmin.com/developer/upload>
with the text and icon in `store/`.
