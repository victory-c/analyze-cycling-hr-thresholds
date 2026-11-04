import Toybox.Activity;
import Toybox.Graphics;
import Toybox.Lang;
import Toybox.System;
import Toybox.Test;

// Mirrors scripts/tests/test_calculate_hr_zones.py and the window tests in
// scripts/tests/test_analyze_field_hr.py. Run: monkeydo <prg> <device> -t

(:test)
function testDualThresholdBoundaries(logger as Test.Logger) as Boolean {
    var lowers = HrModel.zoneLowerBounds(150, 188);
    Test.assert(lowers != null);
    var expected = [136, 150, 170, 188];
    for (var i = 0; i < 4; i++) {
        Test.assertEqual((lowers as Array<Number>)[i], expected[i]);
    }
    return true;
}

(:test)
function testRejectsInvalidAnchorOrder(logger as Test.Logger) as Boolean {
    Test.assert(HrModel.zoneLowerBounds(185, 180) == null);
    Test.assert(HrModel.zoneLowerBounds(0, 180) == null);
    return true;
}

(:test)
function testRejectsEmptyZone(logger as Test.Logger) as Boolean {
    // floor(0.9 * 169) = 152 < VT1 168, so Z3 would be empty.
    Test.assert(HrModel.zoneLowerBounds(168, 169) == null);
    return true;
}

(:test)
function testZoneFor(logger as Test.Logger) as Boolean {
    var lowers = [136, 150, 170, 188];
    Test.assertEqual(HrModel.zoneFor(120, lowers), 1);
    Test.assertEqual(HrModel.zoneFor(136, lowers), 2);
    Test.assertEqual(HrModel.zoneFor(149, lowers), 2);
    Test.assertEqual(HrModel.zoneFor(150, lowers), 3);
    Test.assertEqual(HrModel.zoneFor(187, lowers), 4);
    Test.assertEqual(HrModel.zoneFor(188, lowers), 5);
    return true;
}

(:test)
function testBestWindowTakesHighestRollingMean(logger as Test.Logger) as Boolean {
    var tracker = new HrModel.Tracker([3], 12);
    var hrs = [100, 110, 120, 130, 90];
    for (var t = 0; t < hrs.size(); t++) {
        tracker.addSample(t, hrs[t]);
    }
    Test.assertEqual(tracker.best[0], 120.0);
    return true;
}

(:test)
function testInterpolatesShortGap(logger as Test.Logger) as Boolean {
    // 100 at t=0, 110 at t=10: one run of 11 interpolated seconds.
    var tracker = new HrModel.Tracker([11], 12);
    tracker.addSample(0, 100);
    tracker.addSample(10, 110);
    Test.assertEqual(tracker.best[0], 105.0);
    return true;
}

(:test)
function testLongGapEndsRun(logger as Test.Logger) as Boolean {
    var tracker = new HrModel.Tracker([4], 5);
    for (var t = 0; t < 3; t++) {
        tracker.addSample(t, 150);
    }
    for (var t = 100; t < 103; t++) {
        tracker.addSample(t, 150);
    }
    // Neither run reaches 4 s; the 97 s gap must not be bridged.
    Test.assert(tracker.best[0] == null);
    return true;
}

(:test)
function testIgnoresMissingAndImplausibleHr(logger as Test.Logger) as Boolean {
    var tracker = new HrModel.Tracker([2], 12);
    tracker.addSample(0, 140);
    tracker.addSample(1, null);
    tracker.addSample(2, 300);
    tracker.addSample(3, 140);
    Test.assertEqual(tracker.best[0], 140.0);
    return true;
}

(:test)
function testDomainShares(logger as Test.Logger) as Boolean {
    var tracker = new HrModel.Tracker([2], 12);
    tracker.vt1 = 150;
    tracker.lthr = 188;
    var hrs = [120, 130, 160, 190];
    for (var t = 0; t < hrs.size(); t++) {
        tracker.addSample(t, hrs[t]);
    }
    Test.assertEqual(tracker.domainPct(0), 50);
    Test.assertEqual(tracker.domainPct(1), 25);
    Test.assertEqual(tracker.domainPct(2), 25);
    return true;
}

(:test)
function testFieldRendersEveryLayout(logger as Test.Logger) as Boolean {
    var field = new HrThresholdsField(false);
    var info = new Activity.Info();
    info.timerState = Activity.TIMER_STATE_ON;
    info.currentHeartRate = 172;
    field.compute(info);
    // One-line, third, half and full-page field sizes for this device.
    var settings = System.getDeviceSettings();
    var w = settings.screenWidth;
    var h = settings.screenHeight;
    var sizes = [[w, h / 5], [w, h / 3], [w, h / 2], [w / 2, h / 3], [w, h]];
    for (var i = 0; i < sizes.size(); i++) {
        var options = {:width => sizes[i][0], :height => sizes[i][1]};
        // createBufferedBitmap is CIQ 4+; older Edges construct the bitmap directly.
        var bitmap = (Graphics has :createBufferedBitmap)
            ? Graphics.createBufferedBitmap(options).get() as Graphics.BufferedBitmap
            : new Graphics.BufferedBitmap(options);
        field.onUpdate(bitmap.getDc());
    }
    return true;
}

(:test)
function testFullHourBufferFitsMemory(logger as Test.Logger) as Boolean {
    var before = System.getSystemStats().usedMemory;
    var tracker = new HrModel.Tracker([1200, 1800, 2400, 3600], 12);
    for (var t = 0; t < 3700; t++) {
        tracker.addSample(t, 150 + t % 20);
    }
    var used = System.getSystemStats().usedMemory - before;
    logger.debug("tracker bytes: " + used + ", total used: " + System.getSystemStats().usedMemory + " / " + System.getSystemStats().totalMemory);
    Test.assert(tracker.best[3] != null);
    Test.assert(used < 16384);
    return true;
}

// --- Climb virtual power: mirrors scripts/tests/test_estimate_ftp_without_power_meter.py

function near(actual as Float?, expected as Float, tolerance as Float) as Boolean {
    return actual != null && (actual - expected).abs() <= tolerance;
}

(:test)
function testClimbPowerMatchesPython(logger as Test.Logger) as Boolean {
    // Python: climb_power(82, 10000, 700, 3000, 0.32, 0.005, 1.18, 0, 0.975) -> 213.3 W
    var p = new ClimbModel.Params(82.0, 0.32, 0.005, 0.975, 0.0, 1.18);
    var power = ClimbModel.climbPower(p, 10000.0, 700.0, 3000.0);
    logger.debug("climb power: " + power);
    Test.assert(near(power, 213.3, 0.15));
    return true;
}

(:test)
function testClimbScenariosMatchPython(logger as Test.Logger) as Boolean {
    // Python low/high: (81, 679 m, CdA .28, Crr .004, eff .99, -2 m/s) -> 193.3;
    // (83, 721 m, CdA .36, Crr .006, eff .96, +2 m/s) -> 241.7
    var p = new ClimbModel.Params(82.0, 0.32, 0.005, 0.975, 0.0, 1.18);
    var s = ClimbModel.scenarios(p, 10000.0, 700.0, 3000.0);
    Test.assert(near(s[0], 193.3, 0.15));
    Test.assert(near(s[1], 213.3, 0.15));
    Test.assert(near(s[2], 241.7, 0.15));
    return true;
}

(:test)
function testClimbPowerRejectsInvalidGeometry(logger as Test.Logger) as Boolean {
    var p = new ClimbModel.Params(82.0, 0.32, 0.005, 0.975, 0.0, 1.18);
    Test.assert(ClimbModel.climbPower(p, 100.0, 100.0, 60.0) == null);
    Test.assert(ClimbModel.climbPower(p, 100.0, -1.0, 60.0) == null);
    Test.assert(ClimbModel.climbPower(p, 100.0, 5.0, 0.0) == null);
    return true;
}

(:test)
function testAirDensity(logger as Test.Logger) as Boolean {
    Test.assert(near(ClimbModel.airDensity(101325.0, 20.0), 1.2041, 0.001));
    Test.assert(near(ClimbModel.isaPressure(0.0), 101325.0, 1.0));
    return true;
}

//! 120 s flat at 8 m/s, a 900 s 6 % climb at 4 m/s, then flatSeconds of flat.
function rideClimb(detector as ClimbModel.Detector, climbSeconds as Number, flatSeconds as Number, power as Number?) as Void {
    var d = 0.0;
    var a = 100.0;
    var t = 0;
    for (var i = 0; i < 120; i++) {
        detector.addSample(t, d, a, power, 1.2);
        t++;
        d += 8.0;
    }
    for (var i = 0; i < climbSeconds; i++) {
        detector.addSample(t, d, a, power, 1.2);
        t++;
        d += 4.0;
        a += 0.24;
    }
    for (var i = 0; i < flatSeconds; i++) {
        detector.addSample(t, d, a, power, 1.2);
        t++;
        d += 8.0;
    }
}

function climbParams() as ClimbModel.Params {
    return new ClimbModel.Params(84.0, 0.32, 0.005, 0.975, 0.0, 1.2);
}

(:test)
function testDetectorTrimsClimbToItsEnds(logger as Test.Logger) as Boolean {
    var detector = new ClimbModel.Detector(12);
    detector.params = climbParams();
    rideClimb(detector, 900, 180, null);
    var best = detector.best;
    Test.assert(best != null);
    var climb = best as ClimbModel.Climb;
    logger.debug("climb: " + climb.durationS + " s, " + climb.distanceM + " m, " + climb.gainM + " m, " + climb.powerW);
    // Python: climb_power(84, 3600, 216, 900, 0.32, 0.005, 1.2, 0, 0.975) -> 232.2 W
    Test.assertEqual(climb.durationS, 900);
    Test.assert(near(climb.distanceM, 3600.0, 0.5));
    Test.assert(near(climb.gainM, 216.0, 0.1));
    Test.assert(near(climb.powerW[1], 232.2, 0.3));
    Test.assert(near(climb.powerW[0], 207.2, 0.3));
    Test.assert(near(climb.powerW[2], 267.8, 0.3));
    Test.assert(near(climb.gradePct(), 6.01, 0.02));
    Test.assert(climb.measuredW == null);
    Test.assert(!climb.inFtpWindow());
    return true;
}

(:test)
function testShortClimbIsNotKept(logger as Test.Logger) as Boolean {
    var detector = new ClimbModel.Detector(12);
    detector.params = climbParams();
    rideClimb(detector, 300, 180, null);
    Test.assert(detector.best == null);
    return true;
}

(:test)
function testLongGapEndsClimb(logger as Test.Logger) as Boolean {
    var detector = new ClimbModel.Detector(12);
    detector.params = climbParams();
    var d = 0.0;
    var a = 100.0;
    for (var t = 0; t < 400; t++) {
        detector.addSample(t, d, a, null, 1.2);
        d += 4.0;
        a += 0.24;
    }
    Test.assert(detector.current() != null);
    // A 60 s gap (e.g. a stop with auto-pause off and no samples) closes it.
    detector.addSample(460, d, a, null, 1.2);
    Test.assert(detector.current() == null);
    return true;
}

(:test)
function testNoMassMeansNoClimbPower(logger as Test.Logger) as Boolean {
    var detector = new ClimbModel.Detector(12);
    rideClimb(detector, 900, 180, null);
    Test.assert(detector.best == null);
    return true;
}

(:test)
function testMeterPowerReportedWhenItCoversTheClimb(logger as Test.Logger) as Boolean {
    var detector = new ClimbModel.Detector(12);
    detector.params = climbParams();
    rideClimb(detector, 900, 180, 240);
    var climb = detector.best as ClimbModel.Climb;
    Test.assert(near(climb.measuredW, 240.0, 0.01));
    return true;
}

(:test)
function testFtpWindowFlag(logger as Test.Logger) as Boolean {
    var detector = new ClimbModel.Detector(12);
    detector.params = climbParams();
    rideClimb(detector, 2700, 180, null);
    Test.assert((detector.best as ClimbModel.Climb).inFtpWindow());
    return true;
}

(:test)
function testWorstCaseClimbRowFitsScreen(logger as Test.Logger) as Boolean {
    var w = System.getDeviceSettings().screenWidth;
    var options = {:width => w, :height => 40};
    var bitmap = (Graphics has :createBufferedBitmap)
        ? Graphics.createBufferedBitmap(options).get() as Graphics.BufferedBitmap
        : new Graphics.BufferedBitmap(options);
    var dc = bitmap.getDc();
    // Widest realistic rows on the full-page layout, in both languages, after
    // fitRow() has dropped the range and/or shrunk the font.
    var labels = ["Climb 68' 12.5% FTP?", "Best 68' 12.5% FTP?", "爬坡 68' 12.5% FTP候选", "60'"];
    var full = "1088 W 1012-1199";
    for (var i = 0; i < labels.size(); i++) {
        var value = i == 3 ? "203 (+15)" : full;
        var short = i == 3 ? value : "1012-1199 W";
        var fit = fitRow(dc, w, labels[i], value, short);
        var font = fit[0] as Graphics.FontType;
        var total = dc.getTextWidthInPixels(labels[i], font) + dc.getTextWidthInPixels(fit[1] as String, font) + 3 * ROW_PAD;
        logger.debug(labels[i] + " -> '" + fit[1] + "' width " + total + " / " + w);
        Test.assert(total <= w);
    }
    return true;
}

(:test)
function testStandingAtSummitIsNotClimbTime(logger as Test.Logger) as Boolean {
    // Auto-pause off: 900 s climb, then 600 s standing still with barometric
    // noise. The climb must close at its first summit, not after the stop.
    var detector = new ClimbModel.Detector(12);
    detector.params = climbParams();
    var d = 0.0;
    var a = 100.0;
    var t = 0;
    for (var i = 0; i < 900; i++) {
        detector.addSample(t, d, a, null, 1.2);
        t++;
        d += 4.0;
        a += 0.24;
    }
    var summit = a;
    for (var i = 0; i < 600; i++) {
        detector.addSample(t, d, summit + (i % 7) * 0.1, null, 1.2);
        t++;
    }
    Test.assert(detector.current() == null);
    var climb = detector.best as ClimbModel.Climb;
    logger.debug("summit stop climb: " + climb.durationS + " s");
    Test.assert(climb.durationS <= 900);
    Test.assert(near(climb.powerW[1], 232.2, 1.0));
    return true;
}

(:test)
function testClimbUsesMeanOfStartAndSummitDensity(logger as Test.Logger) as Boolean {
    var detector = new ClimbModel.Detector(12);
    detector.params = climbParams();
    var d = 0.0;
    var a = 100.0;
    // Density falls linearly from 1.25 at the bottom to 1.15 at the top.
    for (var t = 0; t < 1080; t++) {
        var climbing = t >= 120 && t < 1020;
        var progress = t < 120 ? 0.0 : (t >= 1020 ? 1.0 : (t - 120) / 900.0);
        detector.addSample(t, d, a, null, 1.25 - 0.1 * progress);
        d += climbing ? 4.0 : 8.0;
        a += climbing ? 0.24 : 0.0;
    }
    var climb = detector.best as ClimbModel.Climb;
    // Python: climb_power(84, 3600, 216, 900, 0.32, 0.005, 1.2, 0, 0.975) -> 232.2 W
    Test.assert(near(climb.powerW[1], 232.2, 0.3));
    return true;
}
