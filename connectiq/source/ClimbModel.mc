import Toybox.Lang;
import Toybox.Math;

//! Steady-climb virtual power, ported from climb_power() in
//! scripts/estimate_ftp_without_power_meter.py. Never uses heart rate.
module ClimbModel {

    const GRAVITY = 9.80665;
    const DRY_AIR_GAS_CONSTANT = 287.05;

    //! Inputs for one scenario of the physics model.
    class Params {
        public var massKg as Float;
        public var cdaM2 as Float;
        public var crr as Float;
        public var efficiency as Float;
        public var headwindMps as Float;
        public var airDensity as Float;

        public function initialize(massKg as Float, cdaM2 as Float, crr as Float, efficiency as Float, headwindMps as Float, airDensity as Float) {
            self.massKg = massKg;
            self.cdaM2 = cdaM2;
            self.crr = crr;
            self.efficiency = efficiency;
            self.headwindMps = headwindMps;
            self.airDensity = airDensity;
        }
    }

    //! Crank power for a steady climb, or null when the geometry is invalid
    //! (same validation as the Python helper).
    //! P = v * (m g sin(theta) + m g Crr cos(theta) + 0.5 rho CdA v_air |v_air|) / efficiency
    function climbPower(p as Params, distanceM as Float, gainM as Float, durationS as Float) as Float? {
        if (p.massKg <= 0 || distanceM <= 0 || durationS <= 0 || gainM < 0 || gainM >= distanceM) {
            return null;
        }
        if (p.cdaM2 < 0 || p.crr < 0 || p.airDensity <= 0 || p.efficiency <= 0 || p.efficiency > 1) {
            return null;
        }
        var v = distanceM / durationS;
        var theta = Math.asin(gainM / distanceM);
        var vAir = v + p.headwindMps;
        var gravity = p.massKg * GRAVITY * Math.sin(theta);
        var rolling = p.massKg * GRAVITY * p.crr * Math.cos(theta);
        var aero = 0.5 * p.airDensity * p.cdaM2 * vAir * vAir.abs();
        return ((gravity + rolling + aero) * v / p.efficiency).toFloat();
    }

    //! Dry-air density from pressure (Pa) and temperature (deg C).
    function airDensity(pressurePa as Float, tempC as Float) as Float {
        return pressurePa / (DRY_AIR_GAS_CONSTANT * (tempC + 273.15));
    }

    //! ISA pressure (Pa) at an altitude, used when the barometer gives no pressure.
    function isaPressure(altitudeM as Float) as Float {
        return (101325.0 * Math.pow(1.0 - 2.25577e-5 * altitudeM, 5.25588)).toFloat();
    }

    //! Low / base / high crank power for a segment. Every uncertain input moves
    //! in the same direction so the range brackets the base estimate.
    //! Low: CdA -0.04, Crr -0.001, efficiency +1.5 pts, 2 m/s tailwind, mass -1 kg, gain -3 %.
    //! High: the mirror image.
    function scenarios(base as Params, distanceM as Float, gainM as Float, durationS as Float) as Array<Float?> {
        var low = new Params(base.massKg - 1.0, max0(base.cdaM2 - 0.04), max0(base.crr - 0.001),
            min1(base.efficiency + 0.015), base.headwindMps - 2.0, base.airDensity);
        var high = new Params(base.massKg + 1.0, base.cdaM2 + 0.04, base.crr + 0.001,
            base.efficiency - 0.015, base.headwindMps + 2.0, base.airDensity);
        return [
            climbPower(low, distanceM, gainM * 0.97, durationS),
            climbPower(base, distanceM, gainM, durationS),
            climbPower(high, distanceM, gainM * 1.03, durationS),
        ];
    }

    function max0(x as Float) as Float {
        return x > 0 ? x : 0.0;
    }

    function min1(x as Float) as Float {
        return x < 1 ? x : 1.0;
    }

    //! A finished or in-progress climb with its virtual power range.
    class Climb {
        public var durationS as Number;
        public var distanceM as Float;
        public var gainM as Float;
        public var powerW as Array<Float?>;
        public var measuredW as Float?;

        public function initialize(durationS as Number, distanceM as Float, gainM as Float, powerW as Array<Float?>, measuredW as Float?) {
            self.durationS = durationS;
            self.distanceM = distanceM;
            self.gainM = gainM;
            self.powerW = powerW;
            self.measuredW = measuredW;
        }

        public function gradePct() as Float {
            // tan(asin(gain / distance)), matching average_grade_pct in Python.
            var ratio = gainM / distanceM;
            return (100.0 * ratio / Math.sqrt(1.0 - ratio * ratio)).toFloat();
        }

        //! The skill only treats a 40-70 min maximal steady climb as an FTP proxy;
        //! the device cannot judge "maximal", so this flags the duration only.
        public function inFtpWindow() as Boolean {
            return durationS >= 2400 && durationS <= 4200;
        }
    }

    //! Finds steady climbs from 1 Hz distance and barometric altitude.
    //! A climb starts when the trailing 60 s grade reaches 4 % and ends when it
    //! falls below 2 %, the rider drops 15 m below the climb's high point, the
    //! rider covers under 30 m in 60 s (stopped without auto-pause), the timer
    //! pauses, or samples stop for longer than maxGap. The segment runs from the
    //! last low point before the climb to the first time it reached its summit,
    //! so flat road and standing time on either side are not counted.
    class Detector {
        public const WINDOW = 61;
        public const START_GRADE = 0.04;
        public const END_GRADE = 0.02;
        public const MIN_WINDOW_DISTANCE = 100.0;
        public const STALL_DISTANCE = 30.0;
        public const MAX_DROP_M = 15.0;
        public const MIN_CLIMB_S = 600;

        public var maxGap as Number;
        public var params as Params?;
        public var best as Climb? = null;

        private var _t as Array<Number>;
        private var _d as Array<Float>;
        private var _a as Array<Float>;
        private var _p as Array<Number?>;
        private var _rho as Array<Float>;
        private var _count as Number = 0;
        private var _head as Number = 0;
        private var _lastT as Number? = null;

        private var _inClimb as Boolean = false;
        private var _startT as Number = 0;
        private var _startD as Float = 0.0;
        private var _startA as Float = 0.0;
        private var _startRho as Float = 0.0;
        private var _topRho as Float = 0.0;
        private var _nowRho as Float = 0.0;
        private var _topT as Number = 0;
        private var _topD as Float = 0.0;
        private var _topA as Float = 0.0;
        private var _nowT as Number = 0;
        private var _nowD as Float = 0.0;
        private var _nowA as Float = 0.0;
        private var _powerSum as Number = 0;
        private var _powerSeconds as Number = 0;
        private var _topPowerSum as Number = 0;
        private var _topPowerSeconds as Number = 0;

        public function initialize(maxGapSeconds as Number) {
            maxGap = maxGapSeconds;
            _t = new Array<Number>[WINDOW];
            _d = new Array<Float>[WINDOW];
            _a = new Array<Float>[WINDOW];
            _p = new Array<Number?>[WINDOW];
            _rho = new Array<Float>[WINDOW];
        }

        //! Feed one sample. power is from a power meter when present, else null;
        //! density is the current air density in kg/m3.
        public function addSample(t as Number, distanceM as Float?, altitudeM as Float?, power as Number?, density as Float) as Void {
            if (distanceM == null || altitudeM == null) {
                return;
            }
            var lastT = _lastT;
            if (lastT != null) {
                if (t <= lastT) {
                    return;
                }
                if (t - lastT > maxGap) {
                    interrupt();
                }
            }
            _lastT = t;
            _t[_head] = t;
            _d[_head] = distanceM;
            _a[_head] = altitudeM;
            _p[_head] = power;
            _rho[_head] = density;
            _head = (_head + 1) % WINDOW;
            if (_count < WINDOW) {
                _count++;
            }

            if (_inClimb) {
                extend(t, distanceM, altitudeM, power, density);
                var moved = windowDistance();
                if (moved != null && moved < STALL_DISTANCE) {
                    finish();
                    return;
                }
            }
            var grade = trailingGrade();
            if (grade == null) {
                return;
            }
            if (!_inClimb && grade >= START_GRADE) {
                // Start at the last lowest point of the window so flat road
                // before the climb is not counted.
                var oldest = _count < WINDOW ? 0 : _head;
                var start = oldest;
                for (var i = 1; i < _count; i++) {
                    var index = (oldest + i) % WINDOW;
                    if (_a[index] <= _a[start]) {
                        start = index;
                    }
                }
                var offset = (start - oldest + WINDOW) % WINDOW;
                _inClimb = true;
                _startT = _t[start];
                _startD = _d[start];
                _startA = _a[start];
                _startRho = _rho[start];
                _topRho = density;
                _nowRho = density;
                _topT = t;
                _topD = distanceM;
                _topA = altitudeM;
                _nowT = t;
                _nowD = distanceM;
                _nowA = altitudeM;
                // Credit meter power already recorded since the climb start.
                _powerSum = 0;
                _powerSeconds = 0;
                for (var i = offset + 1; i < _count; i++) {
                    var sample = _p[(oldest + i) % WINDOW];
                    if (sample != null && sample >= 0) {
                        _powerSum += sample;
                        _powerSeconds++;
                    }
                }
                _topPowerSum = _powerSum;
                _topPowerSeconds = _powerSeconds;
            } else if (_inClimb && (grade < END_GRADE || altitudeM < _topA - MAX_DROP_M)) {
                finish();
            }
        }

        private function extend(t as Number, distanceM as Float, altitudeM as Float, power as Number?, density as Float) as Void {
            _nowT = t;
            _nowRho = density;
            _nowD = distanceM;
            _nowA = altitudeM;
            if (power != null && power >= 0) {
                _powerSum += power;
                _powerSeconds++;
            }
            // Strictly higher and moving forward: neither a flat run-out at summit
            // height nor barometric noise while standing may move the end.
            if (altitudeM > _topA && distanceM >= _topD + 1.0) {
                _topT = t;
                _topD = distanceM;
                _topA = altitudeM;
                _topRho = density;
                _topPowerSum = _powerSum;
                _topPowerSeconds = _powerSeconds;
            }
        }

        //! Distance covered across the trailing window, or null with under 31 s of samples.
        private function windowDistance() as Float? {
            if (_count < 31) {
                return null;
            }
            var oldest = _count < WINDOW ? 0 : _head;
            var newest = (_head - 1 + WINDOW) % WINDOW;
            return _d[newest] - _d[oldest];
        }

        private function trailingGrade() as Float? {
            var dist = windowDistance();
            if (dist == null || dist < MIN_WINDOW_DISTANCE) {
                return null;
            }
            var oldest = _count < WINDOW ? 0 : _head;
            var newest = (_head - 1 + WINDOW) % WINDOW;
            return (_a[newest] - _a[oldest]) / dist;
        }

        //! Pause, reset or a long gap: close any climb and forget the trailing window.
        public function interrupt() as Void {
            if (_inClimb) {
                finish();
            }
            _count = 0;
            _head = 0;
        }

        private function finish() as Void {
            _inClimb = false;
            var climb = segment(_topT, _topD, _topA, _topRho, _topPowerSum, _topPowerSeconds);
            if (climb == null || climb.durationS < MIN_CLIMB_S) {
                return;
            }
            var current = best;
            var base = climb.powerW[1];
            if (base != null && (current == null || current.powerW[1] == null || base > (current.powerW[1] as Float))) {
                best = climb;
            }
        }

        private function segment(endT as Number, endD as Float, endA as Float, endRho as Float, powerSum as Number, powerSeconds as Number) as Climb? {
            var base = params;
            if (base == null) {
                return null;
            }
            // One density for the whole climb, like the Python helper: the mean
            // of the start and summit values.
            var p = new Params(base.massKg, base.cdaM2, base.crr, base.efficiency, base.headwindMps, (_startRho + endRho) / 2.0);
            var duration = endT - _startT;
            var distance = endD - _startD;
            var gain = endA - _startA;
            if (duration <= 0 || distance <= 0 || gain <= 0) {
                return null;
            }
            var measured = null as Float?;
            // Report meter power only when it covers 90 % of the climb.
            if (powerSeconds * 10 >= duration * 9) {
                measured = powerSum.toFloat() / powerSeconds;
            }
            return new Climb(duration, distance, gain, scenarios(p, distance, gain, duration.toFloat()), measured);
        }

        //! The climb in progress (start to now), or null when not climbing.
        public function current() as Climb? {
            if (!_inClimb) {
                return null;
            }
            return segment(_nowT, _nowD, _nowA, _nowRho, _powerSum, _powerSeconds);
        }
    }
}
