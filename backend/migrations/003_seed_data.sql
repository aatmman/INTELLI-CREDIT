-- ========================================
-- INTELLI-CREDIT: Seed Data for Config Tables
-- Run AFTER 001 and 002 migrations
-- ========================================

-- ========================================
-- Sector Benchmarks (10+ Indian sectors)
-- ========================================
INSERT INTO sector_benchmarks (sector, risk_weight, current_ratio_benchmark, debt_equity_benchmark, dscr_benchmark, interest_coverage_benchmark, ebitda_margin_benchmark, roe_benchmark, pat_margin_benchmark) VALUES
('Manufacturing', 1.0, 1.5, 2.0, 1.5, 3.0, 15.0, 12.0, 8.0),
('IT/Software', 0.8, 2.0, 0.5, 2.5, 5.0, 25.0, 20.0, 15.0),
('NBFC', 2.0, 1.2, 4.0, 1.2, 2.0, 10.0, 15.0, 10.0),
('Infrastructure', 1.5, 1.3, 3.0, 1.3, 2.5, 12.0, 10.0, 6.0),
('Trading', 1.8, 1.2, 2.5, 1.2, 2.0, 5.0, 8.0, 3.0),
('Pharmaceuticals', 0.9, 1.8, 1.5, 2.0, 4.0, 20.0, 18.0, 12.0),
('Textiles', 1.4, 1.3, 2.5, 1.3, 2.5, 10.0, 10.0, 5.0),
('Real Estate', 2.5, 1.0, 3.5, 1.0, 1.5, 15.0, 8.0, 8.0),
('Agriculture', 1.6, 1.2, 2.0, 1.2, 2.0, 12.0, 8.0, 5.0),
('Services', 1.0, 1.5, 1.5, 1.8, 3.5, 18.0, 15.0, 10.0),
('Automobile', 1.2, 1.4, 2.0, 1.5, 3.0, 14.0, 12.0, 7.0),
('Chemicals', 1.1, 1.5, 2.0, 1.5, 3.0, 16.0, 14.0, 9.0),
('Food Processing', 1.0, 1.3, 2.0, 1.5, 3.0, 12.0, 12.0, 6.0),
('Steel/Metals', 1.5, 1.2, 2.5, 1.3, 2.5, 13.0, 10.0, 5.0),
('Education', 0.9, 1.5, 1.0, 2.0, 4.0, 20.0, 15.0, 12.0),
('Healthcare', 0.8, 1.6, 1.5, 2.0, 4.0, 18.0, 16.0, 10.0)
ON CONFLICT (sector) DO NOTHING;

-- ========================================
-- Rate Config (by risk grade)
-- ========================================
INSERT INTO rate_config (risk_grade, base_rate, spread_min, spread_max, effective_rate_min, effective_rate_max, max_exposure_percent, max_tenure_months) VALUES
('A', 7.5, 1.5, 2.5, 9.0, 10.0, 25.0, 84),
('B', 7.5, 2.5, 4.0, 10.0, 11.5, 20.0, 60),
('C', 7.5, 4.0, 6.0, 11.5, 13.5, 15.0, 48),
('D', 7.5, 6.0, 9.0, 13.5, 16.5, 10.0, 36),
('E', 7.5, 9.0, 12.0, 16.5, 19.5, 5.0, 24)
ON CONFLICT (risk_grade) DO NOTHING;

-- ========================================
-- Loan Type Config (with document checklists)
-- ========================================
INSERT INTO loan_type_config (loan_type, loan_type_label, feasibility_score, required_documents, max_tenure_months) VALUES
('CC', 'Cash Credit', 1.0, '[
  {"type": "itr", "label": "Income Tax Returns (3 years)", "required": true, "category": "financial"},
  {"type": "balance_sheet", "label": "Audited Balance Sheet (3 years)", "required": true, "category": "financial"},
  {"type": "bank_statement", "label": "Bank Statements (12 months)", "required": true, "category": "banking"},
  {"type": "gst_return", "label": "GST Returns (24 months)", "required": true, "category": "gst"},
  {"type": "pan_card", "label": "PAN Card", "required": true, "category": "identity"},
  {"type": "cin_certificate", "label": "CIN Certificate", "required": true, "category": "identity"},
  {"type": "board_resolution", "label": "Board Resolution", "required": true, "category": "legal"}
]'::jsonb, 12),
('TL', 'Term Loan', 0.9, '[
  {"type": "itr", "label": "Income Tax Returns (3 years)", "required": true, "category": "financial"},
  {"type": "balance_sheet", "label": "Audited Balance Sheet (3 years)", "required": true, "category": "financial"},
  {"type": "bank_statement", "label": "Bank Statements (12 months)", "required": true, "category": "banking"},
  {"type": "gst_return", "label": "GST Returns (24 months)", "required": true, "category": "gst"},
  {"type": "pan_card", "label": "PAN Card", "required": true, "category": "identity"},
  {"type": "project_report", "label": "Project Report / DPR", "required": true, "category": "project"},
  {"type": "collateral_docs", "label": "Collateral Documents", "required": true, "category": "collateral"}
]'::jsonb, 84),
('WCTL', 'Working Capital Term Loan', 0.85, '[
  {"type": "itr", "label": "Income Tax Returns (3 years)", "required": true, "category": "financial"},
  {"type": "balance_sheet", "label": "Audited Balance Sheet (3 years)", "required": true, "category": "financial"},
  {"type": "bank_statement", "label": "Bank Statements (12 months)", "required": true, "category": "banking"},
  {"type": "gst_return", "label": "GST Returns (24 months)", "required": true, "category": "gst"},
  {"type": "stock_statement", "label": "Stock Statement", "required": true, "category": "collateral"},
  {"type": "debtor_list", "label": "Debtor/Creditor List", "required": true, "category": "financial"}
]'::jsonb, 60),
('BG', 'Bank Guarantee', 0.8, '[
  {"type": "itr", "label": "Income Tax Returns (3 years)", "required": true, "category": "financial"},
  {"type": "balance_sheet", "label": "Audited Balance Sheet (3 years)", "required": true, "category": "financial"},
  {"type": "bank_statement", "label": "Bank Statements (12 months)", "required": true, "category": "banking"},
  {"type": "contract_copy", "label": "Contract/Tender Copy", "required": true, "category": "project"}
]'::jsonb, 36),
('LC', 'Letter of Credit', 0.8, '[
  {"type": "itr", "label": "Income Tax Returns (3 years)", "required": true, "category": "financial"},
  {"type": "balance_sheet", "label": "Audited Balance Sheet (3 years)", "required": true, "category": "financial"},
  {"type": "bank_statement", "label": "Bank Statements (12 months)", "required": true, "category": "banking"},
  {"type": "purchase_order", "label": "Purchase Order", "required": true, "category": "project"}
]'::jsonb, 12)
ON CONFLICT (loan_type) DO NOTHING;

-- ========================================
-- Policy Rules
-- ========================================
INSERT INTO policy_rules (rule_name, rule_code, description, category, is_hard_rule, threshold_field, threshold_operator, threshold_value, failure_message) VALUES
('Minimum Current Ratio', 'MIN_CR', 'Current ratio must be above threshold', 'financial', true, 'current_ratio', 'gte', 1.0, 'Current ratio below minimum 1.0'),
('Maximum Debt-to-Equity', 'MAX_DE', 'Debt-to-equity must not exceed threshold', 'financial', true, 'debt_to_equity', 'lte', 6.0, 'Debt-to-equity exceeds maximum 6.0'),
('Minimum DSCR', 'MIN_DSCR', 'DSCR must be above threshold', 'financial', true, 'dscr', 'gte', 1.0, 'DSCR below minimum 1.0'),
('Maximum Bounce Rate', 'MAX_BOUNCE', 'Cheque bounce rate threshold', 'banking', false, 'bounce_rate', 'lte', 0.15, 'Cheque bounce rate exceeds 15%'),
('NPA Check', 'NPA_CHECK', 'Company must not be flagged as NPA', 'regulatory', true, 'npa_flag', 'eq', 0, 'Company is flagged as NPA'),
('RBI Defaulter Check', 'RBI_DEFAULT', 'Not on RBI wilful defaulter list', 'regulatory', true, 'rbi_caution_flag', 'eq', 0, 'Company found on RBI defaulter list'),
('Circular Trading Score', 'CT_SCORE', 'Circular trading risk threshold', 'gst', false, 'circular_trading_score', 'lte', 60, 'High circular trading risk detected'),
('Minimum Interest Coverage', 'MIN_ICR', 'Interest coverage ratio threshold', 'financial', false, 'interest_coverage', 'gte', 1.5, 'Interest coverage below 1.5x'),
('Maximum Sector Exposure', 'SECTOR_EXP', 'Sector-level exposure limit', 'regulatory', false, 'sector_exposure', 'lte', 25, 'Sector exposure exceeds limit'),
('Minimum Years in Business', 'MIN_YOB', 'Minimum operational history', 'general', false, 'years_in_business', 'gte', 3, 'Less than 3 years in business')
ON CONFLICT (rule_code) DO NOTHING;

-- ========================================
-- Model Config
-- ========================================
INSERT INTO model_config (model_name, model_version, algorithm, file_path, feature_count, training_data_source) VALUES
('pre_qual', 'v1', 'Logistic Regression (L2)', 'ml/models/pre_qual_v1.pkl', 8, 'German Credit + Lending Club'),
('credit_risk', 'v1', 'XGBoost (100 est, depth=6)', 'ml/models/credit_risk_v1.pkl', 28, 'German Credit + Lending Club + Synthetic'),
('circular_trading', 'v1', 'Isolation Forest', 'ml/models/circular_trading_v1.pkl', 5, 'Synthetic GST anomaly data'),
('banking_scorer', 'v1', 'Logistic Regression + Time Series', 'ml/models/banking_scorer_v1.pkl', 12, 'Synthetic banking data')
ON CONFLICT (model_name) DO NOTHING;

-- ========================================
-- Sector Policy
-- ========================================
INSERT INTO sector_policy (sector, status, max_exposure_percent, regulatory_notes) VALUES
('Manufacturing', 'whitelist', 25.0, 'Standard exposure limits apply'),
('IT/Software', 'whitelist', 20.0, 'Low risk sector, favorable terms'),
('NBFC', 'restricted', 10.0, 'RBI regulations on NBFC lending. Enhanced due diligence required'),
('Infrastructure', 'whitelist', 15.0, 'Long gestation period, monitor cash flows closely'),
('Trading', 'restricted', 10.0, 'High circular trading risk. Enhanced GST scrutiny required'),
('Real Estate', 'restricted', 8.0, 'Cyclical sector. RERA compliance mandatory'),
('Agriculture', 'whitelist', 15.0, 'Priority sector lending. Government scheme applicable'),
('Services', 'whitelist', 20.0, 'Standard exposure limits'),
('Pharmaceuticals', 'whitelist', 20.0, 'Regulated sector, stable cash flows'),
('Textiles', 'whitelist', 12.0, 'Seasonal fluctuations. Working capital focus')
ON CONFLICT (sector) DO NOTHING;
