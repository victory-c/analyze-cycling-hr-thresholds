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
