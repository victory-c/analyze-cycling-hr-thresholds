# CPET threshold methods and quality audit

## Principle

Analyze raw breath-by-breath data independently of the lab's HTML report. A polished summary cannot repair an unsuitable protocol, bad time alignment, missing variables, or an unconfirmed maximal effort.

## 1. Inventory before analysis

Record file names, worksheet names, header rows, column names, units, row counts, time format, missingness, duplicated timestamps, sampling interval, and available quality/calibration flags.

At minimum seek elapsed time, HR, VO2, VCO2, VE, RER, VE/VO2, VE/VCO2, PetO2, and PetCO2. Also seek work rate, cadence, stage annotations, respiratory frequency, tidal volume, and stop reason.

Check unit plausibility. VO2/VCO2 may be in mL/min or L/min; ratios are dimensionless; VE is commonly L/min. Do not silently convert ambiguous units.

## 2. Normalize time correctly

Breath-by-breath samples are irregular. Parse elapsed time, sort, reject duplicate or non-increasing timestamps with an audit trail, and regularize onto a one-second grid before time-based smoothing. Prefer time-weighted or interpolation-aware methods and do not bridge long gaps.

Compare 15-, 20-, 30-, and 40-second smoothing windows. A threshold that shifts substantially with modest smoothing choices has low precision.

If an ergometer has a separate clock, align it with the metabolic cart by cross-correlating their HR streams across plausible lags. Report the lag, correlation, bias, and RMSE. Heart-rate agreement can validate alignment while the cart's work-rate channel remains wrong; audit those separately.

## 3. Delimit the exercise segment

Exclude resting baseline and recovery from breakpoint searches. Identify exercise onset and ramp termination from power, VO2/VE rise, protocol markers, or a clearly documented stage schedule. Avoid choosing a threshold near search-window boundaries.

## 4. Locate VT1 / GET

Require convergence of several indicators:

- V-slope: VCO2 begins increasing disproportionately relative to VO2;
- VE/VO2 reaches a nadir and then rises while VE/VCO2 remains stable;
- PetO2 reaches a nadir and then rises without the later compensatory PetCO2 fall;
- ventilatory and metabolic trends are locally coherent rather than driven by one breath.

Segmented regression is a candidate generator, not a substitute for visual and physiological adjudication. The original V-slope paper is [Beaver, Wasserman, and Whipp (1986)](https://pubmed.ncbi.nlm.nih.gov/3087938/).

## 5. Locate VT2 / RCP

Seek convergence of:

- VE/VCO2 reaching its nadir and rising persistently;
- nonlinear acceleration of VE relative to VCO2;
- PetCO2 reaching a peak or plateau and then falling;
- high-intensity behavior that persists over more than a few noisy breaths.

Do not define RCP from RER = 1.00 or another fixed RER. RER is a supporting cross-check affected by protocol, feeding, and hyperventilation.

Ventilatory thresholds can agree with blood-lactate transitions in cycling, but the constructs and measurement error are not identical. See [Solberg et al. (2005)](https://pubmed.ncbi.nlm.nih.gov/16430678/).

## 6. Audit the high end

Before treating final-stage HR as LTHR, RCP, or HRmax, examine:

- achieved HR relative to credible cycling field maxima;
- VO2 plateau or continued rise;
- RER and ventilation behavior;
- cadence decline and premature muscular failure;
- protocol duration and stage size;
- symptoms and stop reason;
- mask, flow, or analyzer-quality notes.

Do not claim a mask leak merely because gases look odd; describe the observed inconsistency and possible explanations. A low-cadence or strength-limited protocol can terminate before cardiovascular maximum. Cadence can change physiological responses and performance: [Formenti et al. (2015)](https://pubmed.ncbi.nlm.nih.gov/22648142/) and [Kounalakis & Geladas (2012)](https://pubmed.ncbi.nlm.nih.gov/28493819/).

## 7. Assign confidence

For each threshold give the time, HR, supporting variables, sensitivity to smoothing, and a plausible HR range. Confidence is:

- high when multiple independent indicators converge and the protocol covers the transition cleanly;
- moderate when most indicators agree but noise, alignment, or protocol limits precision;
- low when indicators conflict, the breakpoint lies at an edge, the high end is truncated, or raw variables are missing.

It is acceptable—and often correct—to identify VT1 but decline to identify LT2/RCP.

