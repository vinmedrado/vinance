from __future__ import annotations

from sklearn.calibration import CalibratedClassifierCV

from .models import PreprocessingBundle


def calibrate_if_applicable(estimator, preprocessing: PreprocessingBundle, validation_frame):
    if not hasattr(estimator, "predict_proba") or len(validation_frame["target_class"].unique()) < 2:
        return estimator, False
    x_validation = preprocessing.transform(validation_frame)
    y_validation = validation_frame["target_class"].astype(int)
    try:
        calibrated = CalibratedClassifierCV(estimator, method="sigmoid", cv="prefit")
        calibrated.fit(x_validation, y_validation)
        return calibrated, True
    except Exception:
        return estimator, False
