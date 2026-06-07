-- Sentinel logical PostgreSQL schema baseline.
-- This file documents the target model. Alembic migrations will be split by owner.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS identity;
CREATE SCHEMA IF NOT EXISTS inventory;
CREATE SCHEMA IF NOT EXISTS relationships;
CREATE SCHEMA IF NOT EXISTS intelligence;
CREATE SCHEMA IF NOT EXISTS operations;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS platform;

CREATE TYPE identity.tenant_status AS ENUM
  ('pending_consent', 'active', 'suspended', 'offboarding', 'offboarded');
CREATE TYPE inventory.resource_state AS ENUM
  ('active', 'missing', 'deleted', 'inaccessible');
CREATE TYPE intelligence.assessment_status AS ENUM
  ('draft', 'assessing', 'assessed', 'failed', 'cancelled', 'expired');
CREATE TYPE intelligence.risk_level AS ENUM ('low', 'medium', 'high');
CREATE TYPE operations.operation_status AS ENUM
  ('draft', 'awaiting_approval', 'ready', 'queued', 'running', 'succeeded',
   'failed', 'cancelled', 'rejected', 'compensating', 'compensated');
CREATE TYPE operations.approval_decision AS ENUM
  ('pending', 'approved', 'rejected', 'expired', 'revoked');

CREATE TABLE platform.outbox (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    destination text NOT NULL,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    status text NOT NULL DEFAULT 'pending',
    attempts integer NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz,
    last_error text
);

CREATE INDEX ix_outbox_pending ON platform.outbox (status, available_at);

CREATE TABLE identity.tenants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entra_tenant_id uuid NOT NULL,
    identity_scope_key text NOT NULL UNIQUE,
    account_type text NOT NULL DEFAULT 'organization',
    display_name text NOT NULL,
    status identity.tenant_status NOT NULL DEFAULT 'pending_consent',
    onboarding_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    consented_at timestamptz,
    suspended_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    version integer NOT NULL DEFAULT 1,
    CONSTRAINT tenants_display_name_nonempty CHECK (length(trim(display_name)) > 0),
    CONSTRAINT tenants_account_type CHECK (account_type IN ('organization', 'personal'))
);

CREATE INDEX ix_tenants_entra_tenant_id ON identity.tenants (entra_tenant_id);

CREATE TABLE identity.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES identity.tenants(id),
    entra_object_id uuid NOT NULL,
    principal_name text,
    display_name text NOT NULL,
    email text,
    is_active boolean NOT NULL DEFAULT true,
    last_login_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    version integer NOT NULL DEFAULT 1,
    UNIQUE (tenant_id, entra_object_id)
);

CREATE INDEX ix_users_tenant_active
    ON identity.users (tenant_id, is_active, display_name);

CREATE TABLE identity.roles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid REFERENCES identity.tenants(id),
    name text NOT NULL,
    description text,
    is_system boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX ux_roles_tenant_name
    ON identity.roles (COALESCE(tenant_id, '00000000-0000-0000-0000-000000000000'), lower(name));

CREATE TABLE identity.permissions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    description text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE identity.role_permissions (
    role_id uuid NOT NULL REFERENCES identity.roles(id) ON DELETE CASCADE,
    permission_id uuid NOT NULL REFERENCES identity.permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE identity.user_roles (
    tenant_id uuid NOT NULL REFERENCES identity.tenants(id),
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    role_id uuid NOT NULL REFERENCES identity.roles(id) ON DELETE CASCADE,
    scope_type text NOT NULL DEFAULT 'tenant',
    scope_id text NOT NULL DEFAULT '*',
    assigned_by uuid REFERENCES identity.users(id),
    assigned_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz,
    PRIMARY KEY (tenant_id, user_id, role_id, scope_type, scope_id)
);

CREATE INDEX ix_user_roles_effective
    ON identity.user_roles (tenant_id, user_id, expires_at);

CREATE TABLE identity.oauth_connections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES identity.tenants(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    provider text NOT NULL DEFAULT 'microsoft',
    token_authority text NOT NULL,
    scopes text NOT NULL,
    encrypted_refresh_token text NOT NULL,
    last_refreshed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, user_id, provider)
);

CREATE INDEX ix_oauth_connections_tenant_user
    ON identity.oauth_connections (tenant_id, user_id);

CREATE TABLE identity.automation_identities (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES identity.tenants(id),
    entra_client_id uuid NOT NULL,
    entra_object_id uuid,
    credential_reference text,
    credential_kind text NOT NULL,
    status text NOT NULL,
    last_validated_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, entra_client_id),
    CONSTRAINT automation_identity_kind CHECK
      (credential_kind IN ('certificate', 'customer_connector_managed_identity'))
);

CREATE TABLE inventory.subscriptions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    azure_subscription_id uuid NOT NULL,
    display_name text NOT NULL,
    state text NOT NULL,
    management_group_id text,
    automation_identity_id uuid,
    last_sync_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    version integer NOT NULL DEFAULT 1,
    UNIQUE (tenant_id, azure_subscription_id)
);

CREATE INDEX ix_subscriptions_tenant_state
    ON inventory.subscriptions (tenant_id, state);

CREATE TABLE inventory.resources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    subscription_id uuid NOT NULL REFERENCES inventory.subscriptions(id),
    azure_resource_id text NOT NULL,
    normalized_resource_id text NOT NULL,
    resource_type text NOT NULL,
    name text NOT NULL,
    resource_group text NOT NULL,
    location text,
    kind text,
    sku text,
    tags jsonb NOT NULL DEFAULT '{}'::jsonb,
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_etag text,
    provisioning_state text,
    state inventory.resource_state NOT NULL DEFAULT 'active',
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    missing_since timestamptz,
    deleted_at timestamptz,
    source_snapshot_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    version integer NOT NULL DEFAULT 1,
    UNIQUE (tenant_id, normalized_resource_id),
    UNIQUE (tenant_id, id),
    CONSTRAINT normalized_resource_id_lowercase CHECK
      (normalized_resource_id = lower(normalized_resource_id))
);

CREATE INDEX ix_resources_tenant_type_state
    ON inventory.resources (tenant_id, resource_type, state);
CREATE INDEX ix_resources_tenant_subscription_group
    ON inventory.resources (tenant_id, subscription_id, resource_group);
CREATE INDEX ix_resources_tenant_name
    ON inventory.resources (tenant_id, lower(name));
CREATE INDEX ix_resources_tags_gin ON inventory.resources USING gin (tags);
CREATE INDEX ix_resources_properties_gin ON inventory.resources USING gin (properties jsonb_path_ops);

CREATE TABLE inventory.resource_groups (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    subscription_id uuid NOT NULL REFERENCES inventory.subscriptions(id),
    name text NOT NULL,
    normalized_name text NOT NULL,
    location text,
    tags jsonb NOT NULL DEFAULT '{}'::jsonb,
    state text NOT NULL DEFAULT 'active',
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, subscription_id, normalized_name)
);

CREATE INDEX ix_resource_groups_tenant_subscription
    ON inventory.resource_groups (tenant_id, subscription_id);

CREATE TABLE inventory.sync_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    requested_by uuid NOT NULL,
    mode text NOT NULL,
    scope jsonb NOT NULL,
    idempotency_key text NOT NULL,
    status text NOT NULL,
    resources_seen bigint NOT NULL DEFAULT 0,
    resources_changed bigint NOT NULL DEFAULT 0,
    error_summary jsonb,
    correlation_id uuid NOT NULL,
    requested_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz,
    heartbeat_at timestamptz,
    CONSTRAINT sync_job_mode CHECK (mode IN ('full', 'incremental', 'resource')),
    UNIQUE (tenant_id, idempotency_key)
);

CREATE INDEX ix_sync_jobs_tenant_requested
    ON inventory.sync_jobs (tenant_id, requested_at DESC);
CREATE INDEX ix_sync_jobs_status_heartbeat
    ON inventory.sync_jobs (status, heartbeat_at);

CREATE TABLE relationships.relationships (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    source_resource_id uuid NOT NULL,
    target_resource_id uuid NOT NULL,
    relationship_type text NOT NULL,
    source_system text NOT NULL,
    dependency_strength text NOT NULL,
    confidence numeric(4,3) NOT NULL,
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    extractor_name text NOT NULL,
    extractor_version text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    first_observed_at timestamptz NOT NULL DEFAULT now(),
    last_observed_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, source_resource_id, target_resource_id, relationship_type, source_system),
    CONSTRAINT relationship_no_self_loop CHECK (source_resource_id <> target_resource_id),
    CONSTRAINT relationship_confidence_range CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT relationship_strength CHECK
      (dependency_strength IN ('hard', 'soft', 'association'))
);

CREATE INDEX ix_relationships_tenant_source_active
    ON relationships.relationships (tenant_id, source_resource_id, is_active);
CREATE INDEX ix_relationships_tenant_target_active
    ON relationships.relationships (tenant_id, target_resource_id, is_active);
CREATE INDEX ix_relationships_tenant_type
    ON relationships.relationships (tenant_id, relationship_type);

CREATE TABLE relationships.resource_nodes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    inventory_resource_id uuid NOT NULL,
    azure_resource_id text NOT NULL,
    normalized_resource_id text NOT NULL,
    name text NOT NULL,
    resource_type text NOT NULL,
    resource_group text NOT NULL,
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, inventory_resource_id),
    UNIQUE (tenant_id, normalized_resource_id)
);

CREATE INDEX ix_resource_nodes_tenant_type
    ON relationships.resource_nodes (tenant_id, resource_type);

CREATE TABLE relationships.graph_snapshots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    root_resource_id uuid NOT NULL,
    direction text NOT NULL,
    max_depth smallint NOT NULL,
    node_count integer NOT NULL,
    edge_count integer NOT NULL,
    inventory_snapshot_id uuid,
    extractor_set_version text NOT NULL,
    content_uri text,
    content_sha256 text NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT graph_direction CHECK (direction IN ('upstream', 'downstream', 'both')),
    CONSTRAINT graph_depth_bounds CHECK (max_depth BETWEEN 1 AND 10)
);

CREATE INDEX ix_graph_snapshots_tenant_root_created
    ON relationships.graph_snapshots (tenant_id, root_resource_id, created_at DESC);

CREATE TABLE intelligence.change_assessments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    requested_by uuid NOT NULL,
    target_resource_id uuid NOT NULL,
    action_type text NOT NULL,
    parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    status intelligence.assessment_status NOT NULL DEFAULT 'draft',
    risk_score smallint,
    risk_level intelligence.risk_level,
    approval_required boolean,
    rule_set_version text,
    inventory_snapshot_id uuid,
    graph_snapshot_id uuid,
    target_etag text,
    canonical_input jsonb NOT NULL,
    input_sha256 text NOT NULL,
    execution_window tstzrange,
    assessed_at timestamptz,
    expires_at timestamptz,
    failure_code text,
    correlation_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    version integer NOT NULL DEFAULT 1,
    UNIQUE (tenant_id, id),
    CONSTRAINT assessment_score_range CHECK (risk_score IS NULL OR risk_score BETWEEN 0 AND 100)
);

CREATE INDEX ix_assessments_tenant_created
    ON intelligence.change_assessments (tenant_id, created_at DESC);
CREATE INDEX ix_assessments_tenant_target
    ON intelligence.change_assessments (tenant_id, target_resource_id, created_at DESC);
CREATE INDEX ix_assessments_tenant_status
    ON intelligence.change_assessments (tenant_id, status);

CREATE TABLE intelligence.assessment_findings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    assessment_id uuid NOT NULL,
    rule_id text NOT NULL,
    severity intelligence.risk_level NOT NULL,
    title text NOT NULL,
    description text NOT NULL,
    evidence jsonb NOT NULL,
    remediation text,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id, assessment_id)
      REFERENCES intelligence.change_assessments (tenant_id, id) ON DELETE CASCADE
);

CREATE INDEX ix_findings_tenant_assessment
    ON intelligence.assessment_findings (tenant_id, assessment_id, severity);

CREATE TABLE operations.operations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    assessment_id uuid NOT NULL,
    assessment_input_sha256 text NOT NULL,
    action_type text NOT NULL,
    target_resource_id uuid NOT NULL,
    requested_by uuid NOT NULL,
    reason text NOT NULL,
    status operations.operation_status NOT NULL DEFAULT 'draft',
    idempotency_key text NOT NULL,
    policy_snapshot jsonb NOT NULL,
    parameters_snapshot jsonb NOT NULL,
    scheduled_for timestamptz,
    started_at timestamptz,
    completed_at timestamptz,
    result_summary jsonb,
    failure_code text,
    correlation_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    version integer NOT NULL DEFAULT 1,
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, idempotency_key)
);

CREATE INDEX ix_operations_tenant_created
    ON operations.operations (tenant_id, created_at DESC);
CREATE INDEX ix_operations_tenant_status
    ON operations.operations (tenant_id, status, scheduled_for);
CREATE INDEX ix_operations_tenant_target
    ON operations.operations (tenant_id, target_resource_id, created_at DESC);

CREATE TABLE operations.approvals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    operation_id uuid NOT NULL,
    approval_stage smallint NOT NULL DEFAULT 1,
    required_permission text NOT NULL DEFAULT 'operations.approve',
    assigned_to_user_id uuid,
    assigned_to_role_id uuid,
    decision operations.approval_decision NOT NULL DEFAULT 'pending',
    decided_by uuid,
    comment text,
    assessment_input_sha256 text NOT NULL,
    requested_at timestamptz NOT NULL DEFAULT now(),
    decided_at timestamptz,
    expires_at timestamptz NOT NULL,
    FOREIGN KEY (tenant_id, operation_id)
      REFERENCES operations.operations (tenant_id, id) ON DELETE CASCADE,
    CONSTRAINT approval_assignee CHECK
      (assigned_to_user_id IS NOT NULL OR assigned_to_role_id IS NOT NULL)
);

CREATE INDEX ix_approvals_tenant_pending
    ON operations.approvals (tenant_id, decision, expires_at);
CREATE INDEX ix_approvals_tenant_operation
    ON operations.approvals (tenant_id, operation_id, approval_stage);

CREATE TABLE operations.execution_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    operation_id uuid NOT NULL,
    attempt_number smallint NOT NULL,
    executor_version text NOT NULL,
    status text NOT NULL,
    azure_request_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    checkpoint jsonb,
    sanitized_result jsonb,
    started_at timestamptz NOT NULL DEFAULT now(),
    heartbeat_at timestamptz,
    completed_at timestamptz,
    FOREIGN KEY (tenant_id, operation_id)
      REFERENCES operations.operations (tenant_id, id) ON DELETE CASCADE,
    UNIQUE (tenant_id, operation_id, attempt_number)
);

CREATE INDEX ix_execution_attempts_running
    ON operations.execution_attempts (status, heartbeat_at);

CREATE TABLE audit.audit_logs (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    event_id uuid NOT NULL,
    occurred_at timestamptz NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    actor_type text NOT NULL,
    actor_id text NOT NULL,
    action text NOT NULL,
    entity_type text NOT NULL,
    entity_id text,
    outcome text NOT NULL,
    source_service text NOT NULL,
    correlation_id uuid NOT NULL,
    trace_id text,
    client_ip inet,
    user_agent text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    previous_hash text,
    record_hash text NOT NULL,
    PRIMARY KEY (occurred_at, id),
    UNIQUE (tenant_id, event_id, occurred_at)
) PARTITION BY RANGE (occurred_at);

-- Monthly partitions are created ahead of time by the audit migration/runbook.
CREATE INDEX ix_audit_logs_tenant_time
    ON audit.audit_logs (tenant_id, occurred_at DESC);
CREATE INDEX ix_audit_logs_tenant_entity
    ON audit.audit_logs (tenant_id, entity_type, entity_id, occurred_at DESC);
CREATE INDEX ix_audit_logs_tenant_correlation
    ON audit.audit_logs (tenant_id, correlation_id);

CREATE TABLE audit.audit_logs_default
    PARTITION OF audit.audit_logs DEFAULT;

CREATE TABLE audit.activity_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    user_id uuid,
    category text NOT NULL,
    message text NOT NULL,
    related_entity_type text,
    related_entity_id text,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX ix_activity_events_tenant_time
    ON audit.activity_events (tenant_id, occurred_at DESC);

CREATE TABLE audit.export_batches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    period_start timestamptz NOT NULL,
    period_end timestamptz NOT NULL,
    status text NOT NULL,
    blob_uri text,
    manifest_sha256 text,
    record_count bigint,
    requested_by uuid,
    requested_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE INDEX ix_export_batches_tenant_period
    ON audit.export_batches (tenant_id, period_start DESC);

-- Representative RLS policy. Each tenant-owned table receives an equivalent policy
-- in its owning service's Alembic migration.
ALTER TABLE inventory.resources ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory.resources FORCE ROW LEVEL SECURITY;
CREATE POLICY resources_tenant_isolation ON inventory.resources
    USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
