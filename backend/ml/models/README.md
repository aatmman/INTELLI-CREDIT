# ML Model Placeholders

This directory holds the trained model `.pkl` files.

## Expected Files

| File | Model | Algorithm | Stage |
|------|-------|-----------|-------|
| `pre_qual_v1.pkl` | Pre-Qualification | Logistic Regression | 0 |
| `credit_risk_v1.pkl` | Credit Risk | XGBoost | 5 |
| `circular_trading_v1.pkl` | Circular Trading | Isolation Forest | 4 |
| `banking_scorer_v1.pkl` | Banking Behavior | Logistic Regression | 4 |
| `config/shap_explainer_v1.pkl` | SHAP Explainer | TreeExplainer | 5 |

## How to Add Models

1. Train models on Google Colab using `ml-training/` notebooks
2. Export using `joblib.dump(model, 'model_name.pkl')`
3. Drop `.pkl` files into this directory
4. The `model_loader.py` will auto-detect and load them at startup
