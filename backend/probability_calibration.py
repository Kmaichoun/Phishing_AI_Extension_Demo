"""Serializable binary isotonic probability calibration for RF bundles."""
import numpy as np
from sklearn.isotonic import IsotonicRegression
from scipy.optimize import minimize, LinearConstraint
from scipy.special import expit, logit
from sklearn.linear_model import LogisticRegression


class ValidationConstrainedSigmoidCalibrator:
    """Experimental sigmoid MLE under validation-tuned operating constraints.

    This is NOT ordinary unconstrained Platt scaling. Validation is tuning data,
    so only an untouched confirmation set can verify the resulting classifier.
    Conditional probabilities/calibration quality are not guaranteed.
    """
    def __init__(self, warning_bounds, blocking_bounds):
        self.classes_ = np.array([0, 1])
        self.warning_bounds = warning_bounds
        self.blocking_bounds = blocking_bounds

    def fit(self, x, y):
        values = np.asarray(x)
        if values.ndim != 2 or values.shape[1] != 1 or set(np.unique(y)) != {0, 1}:
            raise ValueError('One probability feature and both classes required')
        raw = values[:, 0]; labels = np.asarray(y)
        wl, wu = self.warning_bounds; bl, bu = self.blocking_bounds
        if not (wl < wu < bl < bu):
            raise ValueError('Separated feasible warning/block operating intervals required')
        tw, tb = (wl + wu) / 2, (bl + bu) / 2
        slope = (logit(.8) - logit(.6)) / (tb - tw)
        start = [slope, logit(.6) - slope * tw]
        def objective(theta):
            z = theta[0] * raw + theta[1]
            residual = expit(z) - labels
            return float(np.mean(np.logaddexp(0, z) - labels * z)), np.array([np.mean(residual * raw), np.mean(residual)])
        eps = 1e-7
        rows = np.array([[wl, 1], [wu, 1], [bl, 1], [bu, 1]])
        constraint = LinearConstraint(rows,
            [-np.inf, logit(.6) + eps, -np.inf, logit(.8) + eps],
            [logit(.6) - eps, np.inf, logit(.8) - eps, np.inf])
        result = minimize(objective, start, jac=True, method='SLSQP', bounds=[(1e-6, None), (None, None)],
            constraints=[constraint], options={'maxiter': 500, 'ftol': 1e-12})
        if not result.success: raise ValueError('Constrained sigmoid fit failed: ' + result.message)
        self.coef_ = np.array([[result.x[0]]]); self.intercept_ = np.array([result.x[1]])
        self.calibration_log_loss_ = float(result.fun)
        return self

    def predict_proba(self, x):
        values = np.asarray(x)
        if values.ndim != 2 or values.shape[1] != 1:
            raise ValueError('Expected one probability feature')
        p = expit(values[:, 0] * self.coef_[0, 0] + self.intercept_[0])
        return np.column_stack((1 - p, p))


class BrierSigmoidCalibrator:
    """Monotonic sigmoid fitted by Brier loss on independent calibration rows.

    A research alternative to log-loss sigmoid fitting. Weights are optional;
    validation/test data must never be supplied to fit.
    """
    def __init__(self):
        self.classes_ = np.array([0, 1])

    def fit(self, x, y, sample_weight=None):
        values = np.asarray(x)
        if values.ndim != 2 or values.shape[1] != 1 or set(np.unique(y)) != {0, 1}:
            raise ValueError('One probability feature and both classes required')
        labels = np.asarray(y)
        weights = np.ones(len(labels)) if sample_weight is None else np.asarray(sample_weight)
        weights = weights / weights.sum()
        features = np.column_stack((values[:, 0], np.ones(len(labels))))
        initial = LogisticRegression(C=1e6, max_iter=1000).fit(values, labels, sample_weight=sample_weight)
        starts = [[float(initial.coef_[0, 0]), float(initial.intercept_[0])], [1., 0.], [10., -5.]]
        def objective(theta):
            p = expit(features @ theta)
            residual = p - labels
            loss = np.sum(weights * residual**2)
            gradient = features.T @ (2 * weights * residual * p * (1 - p))
            return loss, gradient
        candidates = []
        for start in starts:
            result = minimize(objective, start, jac=True, method='L-BFGS-B',
                bounds=[(0, None), (None, None)], options={'maxiter': 500, 'ftol': 1e-12, 'gtol': 1e-9})
            if result.success: candidates.append(result)
        if not candidates: raise ValueError('Brier sigmoid calibration did not converge')
        result = min(candidates, key=lambda r: r.fun)
        self.coef_ = np.array([[result.x[0]]])
        self.intercept_ = np.array([result.x[1]])
        self.calibration_brier_loss_ = float(result.fun)
        return self

    def predict_proba(self, x):
        values = np.asarray(x)
        if values.ndim != 2 or values.shape[1] != 1:
            raise ValueError('Expected one probability feature')
        p = expit(values[:, 0] * self.coef_[0, 0] + self.intercept_[0])
        return np.column_stack((1 - p, p))


class BetaProbabilityCalibrator:
    """Monotonic beta map: sigmoid(a log(p) - b log(1-p) + c).

    Kull et al., AISTATS 2017; a,b constrained nonnegative. Fit ONLY on
    independent calibration rows; epsilon clipping handles RF endpoints.
    """
    def __init__(self):
        self.classes_ = np.array([0, 1])

    @staticmethod
    def transform(x):
        values = np.asarray(x)
        if values.ndim != 2 or values.shape[1] != 1:
            raise ValueError('Expected one probability feature')
        p = np.clip(values[:, 0], 1e-6, 1 - 1e-6)
        return np.column_stack((np.log(p), -np.log1p(-p), np.ones(len(p))))

    def fit(self, x, y):
        if set(np.unique(y)) != {0, 1}:
            raise ValueError('Both classes required for calibration')
        features = self.transform(x)
        labels = np.asarray(y)
        def objective(theta):
            logits = features @ theta
            loss = np.mean(np.logaddexp(0, logits) - labels * logits)
            gradient = features.T @ (expit(logits) - labels) / len(labels)
            return loss, gradient
        result = minimize(objective, [1., 1., 0.], jac=True, method='L-BFGS-B',
            bounds=[(0, None), (0, None), (None, None)], options={'maxiter': 500})
        if not result.success:
            raise ValueError('Beta calibration did not converge: ' + result.message)
        self.parameters_ = result.x
        return self

    def predict_proba(self, x):
        p = expit(self.transform(x) @ self.parameters_)
        return np.column_stack((1 - p, p))


class IsotonicProbabilityCalibrator:
    def __init__(self):
        self.classes_ = np.array([0, 1])
        self.regressor = IsotonicRegression(out_of_bounds='clip', increasing=True)

    def fit(self, x, y):
        values = np.asarray(x)
        if values.ndim != 2 or values.shape[1] != 1:
            raise ValueError('Expected one probability feature')
        if set(np.unique(y)) != {0, 1}:
            raise ValueError('Both classes required for calibration')
        self.regressor.fit(values[:, 0], y)
        return self

    def predict_proba(self, x):
        values = np.asarray(x)
        if values.ndim != 2 or values.shape[1] != 1:
            raise ValueError('Expected one probability feature')
        p = self.regressor.predict(values[:, 0])
        return np.column_stack((1 - p, p))
