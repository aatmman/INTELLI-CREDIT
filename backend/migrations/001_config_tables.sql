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
