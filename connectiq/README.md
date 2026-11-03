# HR Thresholds — Connect IQ data field

The on-bike half of this skill. It runs the same zone model as
`scripts/calculate_hr_zones.py` and the same best-window rules as
`scripts/analyze_field_hr.py` live on a Garmin Edge, so every ride records the
evidence the desktop analysis looks for.

| On screen | Saved to the FIT session |
|---|---|
| Current HR + Z1–Z5 badge (dual-threshold model) | Best 20 / 30 / 40 / 60 min HR |
| Time below VT1 / VT1–LTHR / at or above LTHR | % time in each of the three domains |
| Best 20–60 min HR and its gap to LTHR | |

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

## Settings (Garmin Connect → device → Connect IQ → HR Thresholds)

| Key | Meaning | Default |
|---|---|---|
| `VT1` | VT1/GET heart rate, bpm | 0 (unset) |
| `LTHR` | Cycling LTHR/LT2, bpm | 0 (unset) |
| `MaxGap` | Longest HR gap to interpolate, seconds | 12 |

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
