import Toybox.Application;
import Toybox.Lang;
import Toybox.WatchUi;

class HrThresholdsApp extends Application.AppBase {
    private var _field as HrThresholdsField?;

    public function initialize() {
        AppBase.initialize();
    }

    public function getInitialView() as [WatchUi.Views] or [WatchUi.Views, WatchUi.InputDelegates] {
        var field = new HrThresholdsField(true);
        _field = field;
        return [field];
    }

    public function onSettingsChanged() as Void {
        var field = _field;
        if (field != null) {
            field.loadSettings();
        }
        WatchUi.requestUpdate();
    }
}
