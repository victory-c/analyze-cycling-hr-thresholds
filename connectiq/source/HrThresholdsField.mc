import Toybox.Activity;
import Toybox.Application;
import Toybox.FitContributor;
import Toybox.Graphics;
import Toybox.Lang;
import Toybox.Time;
import Toybox.UserProfile;
import Toybox.WatchUi;

const WINDOW_SECONDS = [1200, 1800, 2400, 3600];
const WINDOW_LABELS = ["20'", "30'", "40'", "60'"];
const ZONE_COLORS = [Graphics.COLOR_LT_GRAY, Graphics.COLOR_BLUE, Graphics.COLOR_GREEN, Graphics.COLOR_ORANGE, Graphics.COLOR_RED];
const DOMAIN_COLORS = [Graphics.COLOR_BLUE, Graphics.COLOR_ORANGE, Graphics.COLOR_RED];
const ROW_FONTS = [Graphics.FONT_SMALL, Graphics.FONT_TINY, Graphics.FONT_XTINY];
const ROW_PAD = 8;

//! Largest row font, and the full value if it fits beside the label, else the
//! short value. Returns [font, value].
function fitRow(dc as Graphics.Dc, width as Number, label as String, full as String, short as String) as Array {
    for (var f = 0; f < ROW_FONTS.size(); f++) {
        var font = ROW_FONTS[f];
        var labelW = dc.getTextWidthInPixels(label, font) + 3 * ROW_PAD;
        if (labelW + dc.getTextWidthInPixels(full, font) <= width) {
            return [font, full];
        }
        if (labelW + dc.getTextWidthInPixels(short, font) <= width) {
            return [font, short];
        }
    }
    return [ROW_FONTS[ROW_FONTS.size() - 1], short];
}

//! Live HR zones from the athlete's own VT1/LTHR, time in the three
//! physiological domains, best sustained 20-60 minute HR windows, and
//! physics-model virtual power on steady climbs.
class HrThresholdsField extends WatchUi.DataField {
    private var _tracker as HrModel.Tracker;
    private var _vt1 as Number = 0;
    private var _lthr as Number = 0;
    private var _lowers as Array<Number>? = null;
    private var _fromProfile as Boolean = false;
    private var _configError as Boolean = false;
    private var _hr as Number? = null;
    private var _climbs as ClimbModel.Detector;
    private var _climbBase as ClimbModel.Params? = null;
    private var _tempC as Float = 20.0;

    private var _fitBest as Array<FitContributor.Field?>;
    private var _fitDomain as Array<FitContributor.Field?>;
    private var _fitClimb as Array<FitContributor.Field?>;

    private var _strNoHr as String;
    private var _strSetup as String;
    private var _strConfigError as String;
    private var _strDomains as Array<String>;
    private var _strClimb as String;
    private var _strBestClimb as String;

    //! @param recordFit false only in unit tests, where no FIT session exists
    public function initialize(recordFit as Boolean) {
        DataField.initialize();
        _tracker = new HrModel.Tracker(WINDOW_SECONDS, 12);
        _climbs = new ClimbModel.Detector(12);
        _strClimb = WatchUi.loadResource(Rez.Strings.Climb) as String;
        _strBestClimb = WatchUi.loadResource(Rez.Strings.BestClimb) as String;
        _strNoHr = WatchUi.loadResource(Rez.Strings.NoHr) as String;
        _strSetup = WatchUi.loadResource(Rez.Strings.Setup) as String;
        _strConfigError = WatchUi.loadResource(Rez.Strings.ConfigError) as String;
        _strDomains = [
            WatchUi.loadResource(Rez.Strings.DomainLow) as String,
            WatchUi.loadResource(Rez.Strings.DomainMid) as String,
            WatchUi.loadResource(Rez.Strings.DomainHigh) as String,
        ];
        _fitBest = [null, null, null, null];
        _fitDomain = [null, null, null];
        _fitClimb = [null, null, null, null, null];
        if (recordFit) {
            createFitFields();
        }
        loadSettings();
    }

    private function createFitFields() as Void {
        _fitBest = [
            createField("best_20min_hr", 0, FitContributor.DATA_TYPE_FLOAT, {:mesgType => FitContributor.MESG_TYPE_SESSION, :units => "bpm"}),
            createField("best_30min_hr", 1, FitContributor.DATA_TYPE_FLOAT, {:mesgType => FitContributor.MESG_TYPE_SESSION, :units => "bpm"}),
            createField("best_40min_hr", 2, FitContributor.DATA_TYPE_FLOAT, {:mesgType => FitContributor.MESG_TYPE_SESSION, :units => "bpm"}),
            createField("best_60min_hr", 3, FitContributor.DATA_TYPE_FLOAT, {:mesgType => FitContributor.MESG_TYPE_SESSION, :units => "bpm"}),
        ];
        _fitDomain = [
            createField("pct_below_vt1", 4, FitContributor.DATA_TYPE_UINT8, {:mesgType => FitContributor.MESG_TYPE_SESSION, :units => "%"}),
            createField("pct_vt1_to_lthr", 5, FitContributor.DATA_TYPE_UINT8, {:mesgType => FitContributor.MESG_TYPE_SESSION, :units => "%"}),
            createField("pct_above_lthr", 6, FitContributor.DATA_TYPE_UINT8, {:mesgType => FitContributor.MESG_TYPE_SESSION, :units => "%"}),
        ];
        // Data fields get 32 bytes per FIT message: 4x4 + 3x1 + 3x2 + 2 + 4 = 31.
        _fitClimb = [
            createField("climb_virtual_power", 7, FitContributor.DATA_TYPE_UINT16, {:mesgType => FitContributor.MESG_TYPE_SESSION, :units => "W"}),
            createField("climb_virtual_power_low", 8, FitContributor.DATA_TYPE_UINT16, {:mesgType => FitContributor.MESG_TYPE_SESSION, :units => "W"}),
            createField("climb_virtual_power_high", 9, FitContributor.DATA_TYPE_UINT16, {:mesgType => FitContributor.MESG_TYPE_SESSION, :units => "W"}),
            createField("climb_duration", 10, FitContributor.DATA_TYPE_UINT16, {:mesgType => FitContributor.MESG_TYPE_SESSION, :units => "min"}),
            createField("climb_grade", 11, FitContributor.DATA_TYPE_FLOAT, {:mesgType => FitContributor.MESG_TYPE_SESSION, :units => "%"}),
        ];
    }

    //! Re-read thresholds; called at start and whenever settings change in Garmin Connect.
    public function loadSettings() as Void {
        _vt1 = readNumber("VT1");
        _lthr = readNumber("LTHR");
        var maxGap = readNumber("MaxGap");
        _tracker.maxGap = maxGap > 0 ? maxGap : 12;
        _climbs.maxGap = _tracker.maxGap;
        loadClimbSettings();
        _configError = false;
        _fromProfile = false;
        _lowers = null;
        if (_vt1 > 0 && _lthr > 0) {
            _lowers = HrModel.zoneLowerBounds(_vt1, _lthr);
            _configError = _lowers == null;
        }
        if (_lowers == null) {
            // No usable thresholds: colour by the athlete's Garmin cycling zones,
            // but never guess VT1/LTHR from them.
            _lowers = HrModel.profileLowerBounds(UserProfile.getHeartRateZones(UserProfile.HR_ZONE_SPORT_BIKING));
            _fromProfile = _lowers != null;
            _vt1 = 0;
            _lthr = 0;
        }
        _tracker.vt1 = _vt1;
        _tracker.lthr = _lthr;
    }

    private function readNumber(key as String) as Number {
        var value = Application.Properties.getValue(key);
        return value instanceof Number ? value : 0;
    }

    private function readFloat(key as String, fallback as Float) as Float {
        var value = Application.Properties.getValue(key);
        if (value instanceof Float || value instanceof Number) {
            return value.toFloat();
        }
        return fallback;
    }

    //! System mass = rider (setting, else Garmin profile) + bike. Without a
    //! rider mass the climb model stays off rather than assuming one.
    private function loadClimbSettings() as Void {
        var riderKg = readFloat("RiderKg", 0.0);
        if (riderKg <= 0) {
            var grams = UserProfile.getProfile().weight;
            riderKg = grams == null ? 0.0 : grams / 1000.0;
        }
        _tempC = readFloat("TempC", 20.0);
        var base = null as ClimbModel.Params?;
        if (riderKg > 0) {
            base = new ClimbModel.Params(riderKg + readFloat("BikeKg", 9.0), readFloat("CdA", 0.32),
                readFloat("Crr", 0.005), readFloat("Efficiency", 0.975), 0.0, 1.2);
        }
        _climbBase = base;
        _climbs.params = base;
    }

    public function compute(info as Activity.Info) as Void {
        _hr = info.currentHeartRate;
        if (info.timerState != Activity.TIMER_STATE_ON) {
            _climbs.interrupt();
            return;
        }
        var now = Time.now().value();
        _tracker.addSample(now, _hr);
        var base = _climbBase;
        var altitude = info.altitude;
        if (base != null && altitude != null) {
            var pressure = info.ambientPressure;
            base.airDensity = ClimbModel.airDensity(pressure != null ? pressure : ClimbModel.isaPressure(altitude), _tempC);
        }
        _climbs.addSample(now, info.elapsedDistance, altitude, info.currentPower);
        var best = _climbs.best;
        if (best != null) {
            var values = [rounded(best.powerW[1]), rounded(best.powerW[0]), rounded(best.powerW[2]),
                (best.durationS + 30) / 60, best.gradePct()];
            for (var c = 0; c < _fitClimb.size(); c++) {
                var field = _fitClimb[c];
                var value = values[c];
                if (field != null && value != null) {
                    field.setData(value);
                }
            }
        }
        for (var i = 0; i < _fitBest.size(); i++) {
            var value = _tracker.best[i];
            var field = _fitBest[i];
            if (value != null && field != null) {
                field.setData(value);
            }
        }
        for (var d = 0; d < 3; d++) {
            var pct = _tracker.domainPct(d);
            var field = _fitDomain[d];
            if (pct != null && field != null) {
                field.setData(pct);
            }
        }
    }

    private function rounded(value as Float?) as Number? {
        return value == null ? null : (value + 0.5).toNumber();
    }

    public function onTimerReset() as Void {
        _tracker = new HrModel.Tracker(WINDOW_SECONDS, _tracker.maxGap);
        _tracker.vt1 = _vt1;
        _tracker.lthr = _lthr;
        var params = _climbs.params;
        _climbs = new ClimbModel.Detector(_tracker.maxGap);
        _climbs.params = params;
    }

    public function onUpdate(dc as Graphics.Dc) as Void {
        var bg = getBackgroundColor();
        var fg = bg == Graphics.COLOR_BLACK ? Graphics.COLOR_WHITE : Graphics.COLOR_BLACK;
        dc.setColor(fg, bg);
        dc.clear();
        var w = dc.getWidth();
        var h = dc.getHeight();

        if (h < 80) {
            drawCompact(dc, w, h, fg);
        } else if (h < 170) {
            drawMedium(dc, w, h, fg);
        } else {
            drawLarge(dc, w, h, fg);
        }
    }

    private function zone() as Number? {
        var hr = _hr;
        var lowers = _lowers;
        if (hr == null || lowers == null) {
            return null;
        }
        return HrModel.zoneFor(hr, lowers);
    }

    private function hrText() as String {
        var hr = _hr;
        return hr == null ? _strNoHr : hr.toString();
    }

    private function bestText(i as Number) as String {
        var value = _tracker.best[i];
        if (value == null) {
            return "--";
        }
        var text = value.format("%.0f");
        if (_lthr > 0) {
            var delta = (value - _lthr + (value >= _lthr ? 0.5 : -0.5)).toNumber();
            text += delta >= 0 ? " (+" + delta + ")" : " (" + delta + ")";
        }
        return text;
    }

    //! "245 W 228-262" for a climb, or just "245 W" without the range.
    private function climbText(climb as ClimbModel.Climb, withRange as Boolean) as String {
        var p = climb.powerW;
        var base = p[1];
        if (base == null) {
            return "--";
        }
        var text = base.format("%.0f") + " W";
        var low = p[0];
        var high = p[2];
        if (withRange && low != null && high != null) {
            text += " " + low.format("%.0f") + "-" + high.format("%.0f");
        }
        return text;
    }

    private function climbLabel(prefix as String, climb as ClimbModel.Climb) as String {
        var label = prefix + " " + (climb.durationS / 60) + "' " + climb.gradePct().format("%.1f") + "%";
        return climb.inFtpWindow() ? label + "*" : label;
    }

    //! Coloured zone badge, e.g. "Z3"; returns its width.
    private function drawZoneBadge(dc as Graphics.Dc, x as Number, y as Number, font as Graphics.FontType) as Number {
        var z = zone();
        if (z == null) {
            return 0;
        }
        var label = "Z" + z;
        var tw = dc.getTextWidthInPixels(label, font) + 8;
        var th = Graphics.getFontHeight(font);
        dc.setColor(ZONE_COLORS[z - 1], Graphics.COLOR_TRANSPARENT);
        dc.fillRoundedRectangle(x, y, tw, th, 4);
        dc.setColor(z == 1 ? Graphics.COLOR_BLACK : Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        dc.drawText(x + tw / 2, y, font, label, Graphics.TEXT_JUSTIFY_CENTER);
        return tw;
    }

    //! Three-segment bar of time in each physiological domain with % labels.
    private function drawDomainBar(dc as Graphics.Dc, x as Number, y as Number, w as Number, barH as Number, fg as Number, withLabels as Boolean) as Void {
        var total = _tracker.domainTotal();
        if (_lthr == 0) {
            dc.setColor(fg, Graphics.COLOR_TRANSPARENT);
            dc.drawText(x + w / 2, y, Graphics.FONT_XTINY, _configError ? _strConfigError : _strSetup, Graphics.TEXT_JUSTIFY_CENTER);
            return;
        }
        dc.setColor(Graphics.COLOR_LT_GRAY, Graphics.COLOR_TRANSPARENT);
        dc.drawRectangle(x, y, w, barH);
        if (total > 0) {
            var left = x;
            for (var d = 0; d < 3; d++) {
                var segW = d == 2 ? x + w - left : (w * _tracker.domainSeconds[d]) / total;
                if (segW > 0) {
                    dc.setColor(DOMAIN_COLORS[d], Graphics.COLOR_TRANSPARENT);
                    dc.fillRectangle(left, y, segW, barH);
                }
                left += segW;
            }
        }
        if (!withLabels) {
            return;
        }
        dc.setColor(fg, Graphics.COLOR_TRANSPARENT);
        var labelY = y + barH + 1;
        var justify = [Graphics.TEXT_JUSTIFY_LEFT, Graphics.TEXT_JUSTIFY_CENTER, Graphics.TEXT_JUSTIFY_RIGHT];
        var xs = [x, x + w / 2, x + w];
        for (var d = 0; d < 3; d++) {
            var pct = _tracker.domainPct(d);
            dc.drawText(xs[d], labelY, Graphics.FONT_XTINY, _strDomains[d] + " " + (pct == null ? "--" : pct + "%"), justify[d]);
        }
    }

    private function drawCompact(dc as Graphics.Dc, w as Number, h as Number, fg as Number) as Void {
        var font = Graphics.FONT_NUMBER_MILD;
        var text = hrText();
        var tw = dc.getTextWidthInPixels(text, font);
        var badgeFont = Graphics.FONT_SMALL;
        var badgeW = zone() == null ? 0 : dc.getTextWidthInPixels("Z5", badgeFont) + 12;
        var x = (w - tw - badgeW) / 2;
        var y = (h - Graphics.getFontHeight(font)) / 2;
        dc.setColor(fg, Graphics.COLOR_TRANSPARENT);
        dc.drawText(x, y, font, text, Graphics.TEXT_JUSTIFY_LEFT);
        drawZoneBadge(dc, x + tw + 4, (h - Graphics.getFontHeight(badgeFont)) / 2, badgeFont);
        if (_lthr > 0) {
            drawDomainBar(dc, 4, h - 5, w - 8, 4, fg, false);
        }
    }

    private function drawMedium(dc as Graphics.Dc, w as Number, h as Number, fg as Number) as Void {
        var labelFont = Graphics.FONT_XTINY;
        var labelH = Graphics.getFontHeight(labelFont);
        dc.setColor(fg, Graphics.COLOR_TRANSPARENT);
        dc.drawText(6, 2, labelFont, "HR", Graphics.TEXT_JUSTIFY_LEFT);
        var climbing = _climbs.current();
        var corner = climbing == null ? WINDOW_LABELS[0] + " " + bestText(0) : _strClimb + " " + climbText(climbing, false);
        dc.drawText(w - 6, 2, labelFont, corner, Graphics.TEXT_JUSTIFY_RIGHT);

        var font = Graphics.FONT_NUMBER_MEDIUM;
        var text = hrText();
        var tw = dc.getTextWidthInPixels(text, font);
        var badgeFont = Graphics.FONT_MEDIUM;
        var badgeW = zone() == null ? 0 : dc.getTextWidthInPixels("Z5", badgeFont) + 14;
        var barArea = labelH + 10;
        var numH = Graphics.getFontHeight(font);
        var x = (w - tw - badgeW) / 2;
        var y = labelH + (h - labelH - barArea - numH) / 2;
        dc.drawText(x, y, font, text, Graphics.TEXT_JUSTIFY_LEFT);
        drawZoneBadge(dc, x + tw + 6, y + (numH - Graphics.getFontHeight(badgeFont)) / 2, badgeFont);
        drawDomainBar(dc, 6, h - barArea, w - 12, 6, fg, true);
    }

    private function drawLarge(dc as Graphics.Dc, w as Number, h as Number, fg as Number) as Void {
        var labelFont = Graphics.FONT_XTINY;
        var labelH = Graphics.getFontHeight(labelFont);
        dc.setColor(fg, Graphics.COLOR_TRANSPARENT);
        var header = "HR";
        if (_lthr > 0) {
            header += "  VT1 " + _vt1 + " · LTHR " + _lthr;
        } else if (_fromProfile) {
            header += "  Garmin";
        }
        dc.drawText(w / 2, 2, labelFont, header, Graphics.TEXT_JUSTIFY_CENTER);

        var font = Graphics.FONT_NUMBER_HOT;
        var numH = Graphics.getFontHeight(font);
        var text = hrText();
        var tw = dc.getTextWidthInPixels(text, font);
        var badgeFont = Graphics.FONT_LARGE;
        var badgeW = zone() == null ? 0 : dc.getTextWidthInPixels("Z5", badgeFont) + 16;
        var x = (w - tw - badgeW) / 2;
        var y = labelH + 2;
        dc.setColor(fg, Graphics.COLOR_TRANSPARENT);
        dc.drawText(x, y, font, text, Graphics.TEXT_JUSTIFY_LEFT);
        drawZoneBadge(dc, x + tw + 8, y + (numH - Graphics.getFontHeight(badgeFont)) / 2, badgeFont);

        var barY = y + numH + 6;
        drawDomainBar(dc, 8, barY, w - 16, 10, fg, true);

        var rowFont = Graphics.FONT_SMALL;
        var rowH = Graphics.getFontHeight(rowFont);
        var rowsTop = barY + 12 + labelH + 6;
        // 20' and 60' HR always; 30'/40' only stay in the FIT file. Climb rows follow.
        var labels = [WINDOW_LABELS[0], WINDOW_LABELS[3]];
        var values = [bestText(0), bestText(3)];
        var shorts = [values[0], values[1]];
        var climbing = _climbs.current();
        if (climbing != null) {
            labels.add(climbLabel(_strClimb, climbing));
            values.add(climbText(climbing, true));
            shorts.add(climbText(climbing, false));
        }
        var best = _climbs.best;
        if (best != null) {
            labels.add(climbLabel(_strBestClimb, best));
            values.add(climbText(best, true));
            shorts.add(climbText(best, false));
        }
        var rows = labels.size();
        var rowStep = (h - rowsTop - 2) / rows;
        if (rowStep < rowH) {
            rows = (h - rowsTop - 2) / rowH;
            rowStep = rowH;
        }
        dc.setColor(fg, Graphics.COLOR_TRANSPARENT);
        for (var i = 0; i < rows && i < labels.size(); i++) {
            var rowY = rowsTop + i * rowStep;
            var fit = fitRow(dc, w, labels[i], values[i], shorts[i]);
            dc.drawText(ROW_PAD, rowY, fit[0], labels[i], Graphics.TEXT_JUSTIFY_LEFT);
            dc.drawText(w - ROW_PAD, rowY, fit[0], fit[1], Graphics.TEXT_JUSTIFY_RIGHT);
        }
    }
}
