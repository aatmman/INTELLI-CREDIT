"""
ML Model Loader — Singleton ModelRegistry
Loads all 4 models + scalers + configs + SHAP explainer at startup.

Model Files (13 total in backend/ml/models/):
  pre_qual_v1.pkl, pre_qual_scaler_v1.pkl, pre_qual_config_v1.json
  credit_risk_v1.pkl, credit_risk_scaler_v1.pkl, credit_risk_config_v1.json, shap_explainer_v1.pkl
  banking_scorer_v1.pkl, banking_scorer_scaler_v1.pkl, banking_scorer_config_v1.json
  isolation_forest_v1.pkl, circular_trading_scaler_v1.pkl, circular_trading_config_v1.json
"""

import os
import json
import joblib
import time
import pickle
from typing import Any, Dict, Optional

import xgboost as xgb
import pandas as pd
import numpy as np

try:
    from sklearn.base import BaseEstimator
except ImportError:
    BaseEstimator = object


def _resolve_model_path() -> str:
    """Resolve the ML models directory without depending on config.py."""
    # 1. Explicit env var takes priority
    env_path = os.environ.get("ML_MODEL_PATH")
    if env_path and os.path.isdir(env_path):
        return env_path
    # 2. Relative to this file: ml/model_loader.py → ml/models/
    default = os.path.join(os.path.dirname(__file__), "models")
    return default


class ModelRegistry:
    """
    Singleton registry for all ML models, scalers, configs, and explainers.
    Models load only once — subsequent calls return cached instances.
    """

    _instance: Optional["ModelRegistry"] = None

    def __new__(cls) -> "ModelRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._models: Dict[str, Any] = {}
        self._scalers: Dict[str, Any] = {}
        self._configs: Dict[str, Dict] = {}
        self._shap_explainer: Optional[Any] = None
        self._load_errors: Dict[str, str] = {}
        self._loaded = False
        self._initialized = True

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_all(self) -> None:
        """Load all 4 models + scalers + configs + SHAP explainer from disk."""
        if self._loaded:
            return

        base = _resolve_model_path()
        print(f"[ML] Loading models from: {base}")

        # ── Models ──────────────────────────────────────────────
        model_manifest = {
            "pre_qual": {
                "model": "pre_qual_v1.pkl",
                "scaler": "pre_qual_scaler_v1.pkl",
                "config": "pre_qual_config_v1.json",
            },
            "credit_risk": {
                "model": "credit_risk_v1.pkl",
                "scaler": "credit_risk_scaler_v1.pkl",
                "config": "credit_risk_config_v1.json",
            },
            "banking_scorer": {
                "model": "banking_scorer_v1.pkl",
                "scaler": "banking_scorer_scaler_v1.pkl",
                "config": "banking_scorer_config_v1.json",
            },
            "circular_trading": {
                "model": "isolation_forest_v1.pkl",
                "scaler": "circular_trading_scaler_v1.pkl",
                "config": "circular_trading_config_v1.json",
            },
        }

        for name, files in model_manifest.items():
            # Model (.pkl)
            self._models[name] = self._load_pkl(base, files["model"], name)
            # Scaler (.pkl)
            self._scalers[name] = self._load_pkl(base, files["scaler"], f"{name}_scaler")
            # Config (.json)
            self._configs[name] = self._load_json(base, files["config"], f"{name}_config")

        # ── SHAP Explainer ──────────────────────────────────────
        self._shap_explainer = self._load_pkl(base, "shap_explainer_v1.pkl", "shap_explainer")

        # ── Summary ─────────────────────────────────────────────
        loaded_count = sum(1 for v in self._models.values() if v is not None)
        scaler_count = sum(1 for v in self._scalers.values() if v is not None)
        config_count = sum(1 for v in self._configs.values() if v is not None)
        shap_status = "✓" if self._shap_explainer is not None else "✗"

        self._loaded = True
        print(f"[ML] ── Loading complete ──")
        print(f"[ML]   Models : {loaded_count}/4")
        print(f"[ML]   Scalers: {scaler_count}/4")
        print(f"[ML]   Configs: {config_count}/4")
        print(f"[ML]   SHAP   : {shap_status}")

    def _load_pkl(self, base: str, filename: str, label: str) -> Optional[Any]:
        """Load a .pkl file; return None on failure."""
        filepath = os.path.join(base, filename)
        if not os.path.exists(filepath):
            msg = f"File not found: {filepath}"
            self._load_errors[label] = msg
            print(f"[ML] ⚠ {label}: {msg}")
            return None
        try:
            obj = joblib.load(filepath)
            print(f"[ML] ✓ {label} loaded from {filename}")
            return obj
        except Exception as e:
            msg = str(e)
            self._load_errors[label] = msg
            print(f"[ML] ✗ {label} failed: {msg}")
            return None

    def _load_json(self, base: str, filename: str, label: str) -> Optional[Dict]:
        """Load a .json config file; return None on failure."""
        filepath = os.path.join(base, filename)
        if not os.path.exists(filepath):
            msg = f"File not found: {filepath}"
            self._load_errors[label] = msg
            print(f"[ML] ⚠ {label}: {msg}")
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"[ML] ✓ {label} loaded from {filename}")
            return data
        except Exception as e:
            msg = str(e)
            self._load_errors[label] = msg
            print(f"[ML] ✗ {label} failed: {msg}")
            return None

    # ------------------------------------------------------------------
    # Accessor Methods
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load_all()

    # ── Pre-Qualification (Logistic Regression) ─────────────────

    def get_pre_qual_model(self) -> Optional[Any]:
        """Get the pre-qualification model (Logistic Regression)."""
        self._ensure_loaded()
        return self._models.get("pre_qual")

    def get_pre_qual_scaler(self) -> Optional[Any]:
        self._ensure_loaded()
        return self._scalers.get("pre_qual")

    def get_pre_qual_config(self) -> Optional[Dict]:
        self._ensure_loaded()
        return self._configs.get("pre_qual")

    # ── Credit Risk (XGBoost) ───────────────────────────────────

    def get_credit_risk_model(self) -> Optional[Any]:
        """Get the credit risk model (XGBoost)."""
        self._ensure_loaded()
        return self._models.get("credit_risk")

    def get_credit_risk_scaler(self) -> Optional[Any]:
        self._ensure_loaded()
        return self._scalers.get("credit_risk")

    def get_credit_risk_config(self) -> Optional[Dict]:
        self._ensure_loaded()
        return self._configs.get("credit_risk")

    # ── Banking Scorer (Logistic Regression + Time Series) ──────

    def get_banking_scorer_model(self) -> Optional[Any]:
        """Get the banking behavior scoring model."""
        self._ensure_loaded()
        return self._models.get("banking_scorer")

    def get_banking_scorer_scaler(self) -> Optional[Any]:
        self._ensure_loaded()
        return self._scalers.get("banking_scorer")

    def get_banking_scorer_config(self) -> Optional[Dict]:
        self._ensure_loaded()
        return self._configs.get("banking_scorer")

    # ── Circular Trading (Isolation Forest) ─────────────────────

    def get_circular_trading_model(self) -> Optional[Any]:
        """Get the circular trading detection model (Isolation Forest)."""
        self._ensure_loaded()
        return self._models.get("circular_trading")

    def get_circular_trading_scaler(self) -> Optional[Any]:
        self._ensure_loaded()
        return self._scalers.get("circular_trading")

    def get_circular_trading_config(self) -> Optional[Dict]:
        self._ensure_loaded()
        return self._configs.get("circular_trading")

    # ── SHAP Explainer ──────────────────────────────────────────

    def get_shap_explainer(self) -> Optional[Any]:
        """Get the SHAP TreeExplainer for credit risk model."""
        self._ensure_loaded()
        return self._shap_explainer

    # ------------------------------------------------------------------
    # Health Check
    # ------------------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """
        Return which models/scalers/configs loaded successfully.
        Used by the /health endpoint.
        """
        self._ensure_loaded()

        def _status(obj: Optional[Any]) -> str:
            return "loaded" if obj is not None else "not_loaded"

        model_names = ["pre_qual", "credit_risk", "banking_scorer", "circular_trading"]
        models_status = {name: _status(self._models.get(name)) for name in model_names}
        scalers_status = {name: _status(self._scalers.get(name)) for name in model_names}
        configs_status = {name: _status(self._configs.get(name)) for name in model_names}

        total_expected = 13  # 4 models + 4 scalers + 4 configs + 1 SHAP
        total_loaded = (
            sum(1 for v in self._models.values() if v is not None)
            + sum(1 for v in self._scalers.values() if v is not None)
            + sum(1 for v in self._configs.values() if v is not None)
            + (1 if self._shap_explainer is not None else 0)
        )

        return {
            "status": "healthy" if total_loaded == total_expected else "degraded",
            "loaded": f"{total_loaded}/{total_expected}",
            "models": models_status,
            "scalers": scalers_status,
            "configs": configs_status,
            "shap_explainer": _status(self._shap_explainer),
            "errors": self._load_errors if self._load_errors else None,
        }

    # Legacy compat (used by other modules via get_model("name"))
    def get_model(self, name: str) -> Optional[Any]:
        """Generic accessor — kept for backward compatibility."""
        self._ensure_loaded()
        return self._models.get(name)

    def get_scaler(self, name: str) -> Optional[Any]:
        """Generic scaler accessor."""
        self._ensure_loaded()
        return self._scalers.get(name)

    def get_config(self, name: str) -> Optional[Dict]:
        """Generic config accessor."""
        self._ensure_loaded()
        return self._configs.get(name)

    def get_explainer(self, name: str = "shap_explainer") -> Optional[Any]:
        """Alias for get_shap_explainer (backward compat)."""
        return self.get_shap_explainer()

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def status(self) -> Dict[str, str]:
        """Quick status dict (backward compat — used by /health)."""
        self._ensure_loaded()
        return {
            name: "loaded" if model is not None else "not_loaded"
            for name, model in self._models.items()
        }


# ------------------------------------------------------------------
# Singleton + convenience helpers
# ------------------------------------------------------------------

model_registry = ModelRegistry()


def get_model(name: str) -> Optional[Any]:
    """Convenience: get a model by name."""
    return model_registry.get_model(name)


def load_all_models() -> dict:
    """Called at FastAPI startup (main.py lifespan)."""
    model_registry.load_all()
    return model_registry.status()
