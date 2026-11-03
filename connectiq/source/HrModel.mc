import Toybox.Lang;

//! Pure threshold logic, ported from scripts/calculate_hr_zones.py and
//! scripts/analyze_field_hr.py so the device and the desktop helpers agree.
module HrModel {

    //! Lower BPM bounds of Z2..Z5 for the dual-threshold five-zone model, or
    //! null when the anchors are invalid or rounding empties a zone.
    //! Integer division gives floor(0.90 * x) exactly, matching the Python helper.
    function zoneLowerBounds(vt1 as Number, lthr as Number) as Array<Number>? {
        if (vt1 < 30 || vt1 >= lthr || lthr > 260) {
            return null;
        }
        var z1Upper = (9 * vt1) / 10;
        var z3Upper = (9 * lthr) / 10;
        if (z1Upper + 1 > vt1 - 1 || vt1 > z3Upper || z3Upper + 1 > lthr - 1) {
            return null;
        }
        return [z1Upper + 1, vt1, z3Upper + 1, lthr];
    }

    //! Garmin profile zones ([z1 min, z1 max, ..., z5 max]) as Z2..Z5 lower bounds.
    function profileLowerBounds(zones as Array<Number>?) as Array<Number>? {
        if (zones == null || zones.size() < 5) {
            return null;
        }
        return [zones[1] + 1, zones[2] + 1, zones[3] + 1, zones[4] + 1];
    }

    //! Zone number 1..5 for an HR value given Z2..Z5 lower bounds.
    function zoneFor(hr as Number, lowers as Array<Number>) as Number {
        var zone = 1;
        for (var i = 0; i < lowers.size(); i++) {
            if (hr >= lowers[i]) {
                zone = i + 2;
            }
        }
        return zone;
    }

    //! Physiological domain 0..2: below VT1, VT1 through below LTHR, at or above LTHR.
    function domainFor(hr as Number, vt1 as Number, lthr as Number) as Number {
        if (hr >= lthr) {
            return 2;
        }
        return hr >= vt1 ? 1 : 0;
    }

    //! Best continuous rolling-window HR means over 1 Hz runs.
    //! Gaps up to maxGap seconds are linearly interpolated; longer gaps (sensor
    //! dropout, auto-pause) end the run, exactly like interpolate_seconds().
    class Tracker {
        public var windows as Array<Number>;
        public var best as Array<Float?>;
        public var domainSeconds as Array<Number> = [0, 0, 0];
        public var vt1 as Number = 0;
        public var lthr as Number = 0;
        public var maxGap as Number;

        private var _buf as ByteArray;
        private var _size as Number;
        private var _idx as Number = 0;
        private var _runLen as Number = 0;
        private var _sums as Array<Number>;
        private var _lastT as Number? = null;
        private var _lastHr as Number = 0;

        public function initialize(windowSeconds as Array<Number>, maxGapSeconds as Number) {
            windows = windowSeconds;
            maxGap = maxGapSeconds;
            _size = 1;
            for (var i = 0; i < windows.size(); i++) {
                if (windows[i] > _size) {
                    _size = windows[i];
                }
            }
            _buf = new [_size]b;
            _sums = new Array<Number>[windows.size()];
            best = new Array<Float?>[windows.size()];
            for (var i = 0; i < windows.size(); i++) {
                _sums[i] = 0;
            }
        }

        //! Feed one observation; t is wall-clock seconds, hr may be null.
        public function addSample(t as Number, hr as Number?) as Void {
            if (hr == null || hr < 25 || hr > 260) {
                return;
            }
            var lastT = _lastT;
            if (lastT == null) {
                push(hr);
            } else {
                var gap = t - lastT;
                if (gap <= 0) {
                    return;
                }
                if (gap > maxGap) {
                    breakRun();
                    push(hr);
                } else {
                    var delta = hr - _lastHr;
                    for (var step = 1; step <= gap; step++) {
                        var value = _lastHr + delta * step / gap.toFloat();
                        push((value + 0.5).toNumber());
                    }
                }
            }
            _lastT = t;
            _lastHr = hr;
        }

        public function breakRun() as Void {
            _runLen = 0;
            for (var i = 0; i < _sums.size(); i++) {
                _sums[i] = 0;
            }
        }

        private function push(hr as Number) as Void {
            // Subtract the sample leaving each window before the slot is overwritten.
            for (var i = 0; i < windows.size(); i++) {
                if (_runLen >= windows[i]) {
                    _sums[i] -= _buf[(_idx - windows[i] + _size) % _size];
                }
                _sums[i] += hr;
            }
            _buf[_idx] = hr;
            _idx = (_idx + 1) % _size;
            _runLen++;
            for (var i = 0; i < windows.size(); i++) {
                if (_runLen >= windows[i]) {
                    var mean = _sums[i].toFloat() / windows[i];
                    var current = best[i];
                    if (current == null || mean > current) {
                        best[i] = mean;
                    }
                }
            }
            if (lthr > 0) {
                domainSeconds[domainFor(hr, vt1, lthr)]++;
            }
        }

        public function domainTotal() as Number {
            return domainSeconds[0] + domainSeconds[1] + domainSeconds[2];
        }

        //! Whole-percent share of time in a domain, or null with no data.
        public function domainPct(domain as Number) as Number? {
            var total = domainTotal();
            if (total == 0) {
                return null;
            }
            return (100.0 * domainSeconds[domain] / total + 0.5).toNumber();
        }
    }
}
