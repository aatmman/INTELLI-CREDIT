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
