-- ========================================
-- INTELLI-CREDIT: Config Tables Migration
-- Run this first in Supabase SQL Editor
-- ========================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ========================================
-- 1. sector_benchmarks
-- ========================================
CREATE TABLE IF NOT EXISTS sector_benchmarks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sector VARCHAR(100) NOT NULL UNIQUE,
    risk_weight DECIMAL(4,2) NOT NULL DEFAULT 1.0,
    current_ratio_benchmark DECIMAL(6,2),
    debt_equity_benchmark DECIMAL(6,2),
    dscr_benchmark DECIMAL(6,2),
    interest_coverage_benchmark DECIMAL(6,2),
    ebitda_margin_benchmark DECIMAL(6,2),
    roe_benchmark DECIMAL(6,2),
    pat_margin_benchmark DECIMAL(6,2),
    revenue_growth_benchmark DECIMAL(6,2),
    npa_threshold DECIMAL(6,2),
    additional_benchmarks JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========================================
-- 2. policy_rules
-- ========================================
CREATE TABLE IF NOT EXISTS policy_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rule_name VARCHAR(200) NOT NULL,
    rule_code VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    category VARCHAR(50) NOT NULL, -- financial | gst | banking | collateral | regulatory
    rule_type VARCHAR(20) DEFAULT 'threshold', -- threshold | range | boolean | formula
    is_hard_rule BOOLEAN DEFAULT FALSE,
    threshold_field VARCHAR(100),
    threshold_operator VARCHAR(10), -- gt | lt | gte | lte | eq | between
    threshold_value DECIMAL(12,4),
    threshold_max_value DECIMAL(12,4),
    failure_message TEXT,
    applies_to_loan_types TEXT[] DEFAULT '{}',
    applies_to_sectors TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========================================
-- 3. model_config
-- ========================================
CREATE TABLE IF NOT EXISTS model_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_name VARCHAR(100) NOT NULL UNIQUE,
    model_version VARCHAR(20) NOT NULL,
    algorithm VARCHAR(50) NOT NULL,
    file_path VARCHAR(500),
    feature_count INTEGER,
    feature_names TEXT[],
    performance_metrics JSONB DEFAULT '{}',
    training_data_source VARCHAR(200),
    training_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========================================
-- 4. rate_config
-- ========================================
CREATE TABLE IF NOT EXISTS rate_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    risk_grade VARCHAR(2) NOT NULL UNIQUE,
    base_rate DECIMAL(5,2) NOT NULL,
    spread_min DECIMAL(5,2) NOT NULL,
    spread_max DECIMAL(5,2) NOT NULL,
    effective_rate_min DECIMAL(5,2) NOT NULL,
    effective_rate_max DECIMAL(5,2) NOT NULL,
    max_exposure_percent DECIMAL(5,2),
    max_tenure_months INTEGER,
    processing_fee_percent DECIMAL(5,2) DEFAULT 1.0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========================================
-- 5. loan_type_config
-- ========================================
CREATE TABLE IF NOT EXISTS loan_type_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    loan_type VARCHAR(10) NOT NULL UNIQUE,
    loan_type_label VARCHAR(100) NOT NULL,
    description TEXT,
    feasibility_score DECIMAL(3,2) DEFAULT 1.0,
    required_documents JSONB DEFAULT '[]',
    max_tenure_months INTEGER,
    min_amount DECIMAL(15,2),
    max_amount DECIMAL(15,2),
    collateral_required BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========================================
-- 6. sector_policy
-- ========================================
CREATE TABLE IF NOT EXISTS sector_policy (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sector VARCHAR(100) NOT NULL UNIQUE,
    status VARCHAR(20) DEFAULT 'whitelist', -- whitelist | blacklist | restricted
    max_exposure_percent DECIMAL(5,2),
    special_conditions TEXT,
    regulatory_notes TEXT,
    last_reviewed DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========================================
-- Indexes
-- ========================================
CREATE INDEX IF NOT EXISTS idx_sector_benchmarks_sector ON sector_benchmarks(sector);
CREATE INDEX IF NOT EXISTS idx_policy_rules_category ON policy_rules(category);
CREATE INDEX IF NOT EXISTS idx_policy_rules_active ON policy_rules(is_active);
CREATE INDEX IF NOT EXISTS idx_rate_config_grade ON rate_config(risk_grade);
CREATE INDEX IF NOT EXISTS idx_loan_type_config_type ON loan_type_config(loan_type);
CREATE INDEX IF NOT EXISTS idx_sector_policy_sector ON sector_policy(sector);



-- ========================================
-- INTELLI-CREDIT: Application Tables Migration
-- Run AFTER 001_config_tables.sql
-- ========================================

-- ========================================
-- 1. loan_applications (Core)
-- ========================================
CREATE TABLE IF NOT EXISTS loan_applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_name VARCHAR(300) NOT NULL,
    cin_number VARCHAR(30),
    pan_number VARCHAR(15),
    sector VARCHAR(100) NOT NULL,
    loan_type VARCHAR(10) NOT NULL,
    loan_amount_requested DECIMAL(15,2) NOT NULL,
    annual_turnover DECIMAL(15,2),
    years_in_business INTEGER,
    contact_email VARCHAR(200),
    contact_phone VARCHAR(20),
    borrower_uid VARCHAR(200) NOT NULL,
    assigned_rm VARCHAR(200),
    assigned_analyst VARCHAR(200),
    assigned_cm VARCHAR(200),
    current_stage VARCHAR(30) DEFAULT 'pre_qualification',
    stage_history JSONB DEFAULT '[]',
    pre_qual_score DECIMAL(6,2),
    pre_qual_data JSONB DEFAULT '{}',
    final_risk_grade VARCHAR(2),
    is_active BOOLEAN DEFAULT TRUE,
    remarks TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========================================
-- 2. documents
-- ========================================
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES loan_applications(id) ON DELETE CASCADE,
    document_type VARCHAR(50) NOT NULL,
    file_name VARCHAR(500) NOT NULL,
    file_url TEXT NOT NULL,
    file_size INTEGER,
    mime_type VARCHAR(100),
    status VARCHAR(30) DEFAULT 'uploaded',
    financial_year VARCHAR(10),
    extraction_confidence DECIMAL(5,3),
    extracted_data JSONB DEFAULT '{}',
    parsing_error TEXT,
    uploaded_by VARCHAR(200),
    uploaded_at TIMESTAMPTZ DEFAULT NOW(),
    parsed_at TIMESTAMPTZ,
    verified_by VARCHAR(200),
    verified_at TIMESTAMPTZ,
    verification_remarks TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========================================
-- 3. extracted_financials
-- ========================================
CREATE TABLE IF NOT EXISTS extracted_financials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES loan_applications(id) ON DELETE CASCADE,
    financial_year VARCHAR(10) NOT NULL,
    total_revenue DECIMAL(15,2),
    cost_of_goods DECIMAL(15,2),
    ebitda DECIMAL(15,2),
    pat DECIMAL(15,2),
    total_assets DECIMAL(15,2),
    total_liabilities DECIMAL(15,2),
    net_worth DECIMAL(15,2),
    total_debt DECIMAL(15,2),
    current_assets DECIMAL(15,2),
    current_liabilities DECIMAL(15,2),
    cfo DECIMAL(15,2),
    current_ratio DECIMAL(8,4),
    debt_to_equity DECIMAL(8,4),
    dscr DECIMAL(8,4),
    interest_coverage DECIMAL(8,4),
    ebitda_margin DECIMAL(8,4),
    roe DECIMAL(8,4),
    pat_margin DECIMAL(8,4),
    revenue_cagr DECIMAL(8,4),
    raw_balance_sheet JSONB DEFAULT '{}',
    raw_profit_loss JSONB DEFAULT '{}',
    raw_cash_flow JSONB DEFAULT '{}',
    source_document_id UUID REFERENCES documents(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========================================
-- 4. gst_monthly_data
-- ========================================
CREATE TABLE IF NOT EXISTS gst_monthly_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES loan_applications(id) ON DELETE CASCADE,
    month VARCHAR(7) NOT NULL,
    gstr3b_turnover DECIMAL(15,2),
    gstr1_turnover DECIMAL(15,2),
    itc_claimed DECIMAL(15,2),
    itc_available DECIMAL(15,2),
    itc_reversal DECIMAL(15,2),
    tax_paid DECIMAL(15,2),
    filing_status VARCHAR(20) DEFAULT 'filed',
    mismatch_amount DECIMAL(15,2),
    late_fee DECIMAL(10,2),
    source_document_id UUID REFERENCES documents(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========================================
-- 5. bank_statement_data
-- ========================================
CREATE TABLE IF NOT EXISTS bank_statement_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES loan_applications(id) ON DELETE CASCADE,
    month VARCHAR(7) NOT NULL,
    bank_name VARCHAR(100),
    account_number VARCHAR(30),
    total_credits DECIMAL(15,2),
    total_debits DECIMAL(15,2),
    closing_balance DECIMAL(15,2),
    average_balance DECIMAL(15,2),
    bounce_count INTEGER DEFAULT 0,
    bounce_amount DECIMAL(15,2) DEFAULT 0,
    cash_withdrawals DECIMAL(15,2) DEFAULT 0,
    emi_outflows DECIMAL(15,2) DEFAULT 0,
    source_document_id UUID REFERENCES documents(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========================================
-- 6. field_visit_notes
-- ========================================
CREATE TABLE IF NOT EXISTS field_visit_notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES loan_applications(id) ON DELETE CASCADE,
    visit_date TIMESTAMPTZ NOT NULL,
    visited_by VARCHAR(200),
    capacity_utilization_percent DECIMAL(5,2),
    factory_condition VARCHAR(30),
    inventory_level VARCHAR(30),
    machinery_condition VARCHAR(30),
    management_cooperation VARCHAR(30),
    management_quality VARCHAR(30),
    promoter_presence BOOLEAN DEFAULT TRUE,
    observations TEXT NOT NULL,
    neighborhood_info TEXT,
    employee_count_observed INTEGER,
    photo_urls TEXT[] DEFAULT '{}',
    voice_record_url TEXT,
    additional_notes JSONB DEFAULT '{}',
    risk_adjustments JSONB DEFAULT '{}',
    qualitative_score DECIMAL(6,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========================================
-- 7. research_findings
-- ========================================
CREATE TABLE IF NOT EXISTS research_findings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES loan_applications(id) ON DELETE CASCADE,
    source VARCHAR(30) NOT NULL,
    title VARCHAR(500) NOT NULL,
    summary TEXT,
    url TEXT,
    published_date TIMESTAMPTZ,
    severity VARCHAR(20) DEFAULT 'low',
    risk_impact TEXT,
    risk_points DECIMAL(6,2) DEFAULT 0,
    category VARCHAR(30),
    raw_data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========================================
-- 8. risk_scores
-- ========================================
CREATE TABLE IF NOT EXISTS risk_scores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL UNIQUE REFERENCES loan_applications(id) ON DELETE CASCADE,
    pre_qual_score DECIMAL(6,2),
    financial_score DECIMAL(6,2),
    gst_score DECIMAL(6,2),
    banking_conduct_score DECIMAL(6,2),
    circular_trading_score DECIMAL(6,2),
    qualitative_score DECIMAL(6,2),
    research_risk_score DECIMAL(6,2),
    final_risk_score DECIMAL(6,2),
    risk_grade VARCHAR(2),
    probability_of_default DECIMAL(8,6),
    recommended_limit DECIMAL(15,2),
    recommended_rate DECIMAL(5,2),
    recommended_tenure_months INTEGER,
    shap_values JSONB DEFAULT '[]',
    features_used JSONB DEFAULT '{}',
    policy_check_results JSONB DEFAULT '{}',
    timeline_data JSONB DEFAULT '[]',
    model_version VARCHAR(30),
    scored_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========================================
-- 9. loan_decisions
-- ========================================
CREATE TABLE IF NOT EXISTS loan_decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES loan_applications(id) ON DELETE CASCADE,
    action VARCHAR(40) NOT NULL,
    decided_by VARCHAR(200) NOT NULL,
    decided_by_role VARCHAR(30) NOT NULL,
    approved_limit DECIMAL(15,2),
    approved_rate DECIMAL(5,2),
    approved_tenure_months INTEGER,
    conditions TEXT[] DEFAULT '{}',
    covenants TEXT[] DEFAULT '{}',
    rejection_reason TEXT,
    return_instructions TEXT,
    remarks TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========================================
-- 10. cam_documents
-- ========================================
CREATE TABLE IF NOT EXISTS cam_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES loan_applications(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'generating',
    cam_content JSONB DEFAULT '{}',
    cam_narrative TEXT,
    cam_docx_url TEXT,
    cam_pdf_url TEXT,
    generated_by VARCHAR(200),
    last_edited_by VARCHAR(200),
    completed_at TIMESTAMPTZ,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========================================
-- 11. audit_logs
-- ========================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(200) NOT NULL,
    action VARCHAR(100) NOT NULL,
    performed_by VARCHAR(200),
    details JSONB DEFAULT '{}',
    ip_address VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========================================
-- Agent Progress (for Supabase Realtime)
-- ========================================
CREATE TABLE IF NOT EXISTS agent_progress (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES loan_applications(id) ON DELETE CASCADE,
    agent_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    progress_percent DECIMAL(5,2) DEFAULT 0,
    message TEXT,
    data JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(application_id, agent_name)
);

-- ========================================
-- Indexes
-- ========================================
CREATE INDEX IF NOT EXISTS idx_loan_apps_borrower ON loan_applications(borrower_uid);
CREATE INDEX IF NOT EXISTS idx_loan_apps_stage ON loan_applications(current_stage);
CREATE INDEX IF NOT EXISTS idx_loan_apps_rm ON loan_applications(assigned_rm);
CREATE INDEX IF NOT EXISTS idx_loan_apps_analyst ON loan_applications(assigned_analyst);
CREATE INDEX IF NOT EXISTS idx_loan_apps_cm ON loan_applications(assigned_cm);
CREATE INDEX IF NOT EXISTS idx_loan_apps_active ON loan_applications(is_active);

CREATE INDEX IF NOT EXISTS idx_documents_app ON documents(application_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);

CREATE INDEX IF NOT EXISTS idx_financials_app ON extracted_financials(application_id);
CREATE INDEX IF NOT EXISTS idx_financials_year ON extracted_financials(financial_year);

CREATE INDEX IF NOT EXISTS idx_gst_app ON gst_monthly_data(application_id);
CREATE INDEX IF NOT EXISTS idx_gst_month ON gst_monthly_data(month);

CREATE INDEX IF NOT EXISTS idx_bank_app ON bank_statement_data(application_id);

CREATE INDEX IF NOT EXISTS idx_field_visit_app ON field_visit_notes(application_id);

CREATE INDEX IF NOT EXISTS idx_research_app ON research_findings(application_id);
CREATE INDEX IF NOT EXISTS idx_research_severity ON research_findings(severity);

CREATE INDEX IF NOT EXISTS idx_risk_scores_app ON risk_scores(application_id);

CREATE INDEX IF NOT EXISTS idx_decisions_app ON loan_decisions(application_id);

CREATE INDEX IF NOT EXISTS idx_cam_app ON cam_documents(application_id);

CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(created_at);

CREATE INDEX IF NOT EXISTS idx_agent_progress_app ON agent_progress(application_id);

-- ========================================
-- Enable RLS on all application tables
-- ========================================
ALTER TABLE loan_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE extracted_financials ENABLE ROW LEVEL SECURITY;
ALTER TABLE gst_monthly_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE bank_statement_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE field_visit_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE loan_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE cam_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_progress ENABLE ROW LEVEL SECURITY;

-- Service role bypass (for backend using service_role_key)
CREATE POLICY "Service role full access" ON loan_applications FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON documents FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON extracted_financials FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON gst_monthly_data FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON bank_statement_data FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON field_visit_notes FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON research_findings FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON risk_scores FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON loan_decisions FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON cam_documents FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON audit_logs FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON agent_progress FOR ALL USING (TRUE) WITH CHECK (TRUE);

-- Enable Realtime for agent_progress (live updates to frontend)
ALTER PUBLICATION supabase_realtime ADD TABLE agent_progress;


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



SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public';
