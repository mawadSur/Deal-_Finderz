-- Table for storing Zillow contact information
CREATE TABLE IF NOT EXISTS app.zillow_contacts (
    id BIGSERIAL PRIMARY KEY,
    deal_id BIGINT NOT NULL REFERENCES app.deals(id) ON DELETE CASCADE,
    zillow_id TEXT NOT NULL,
    agent_name TEXT,
    agent_phone TEXT,
    agent_email TEXT,
    brokerage TEXT,
    contact_source TEXT DEFAULT 'zillow_api',
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS zillow_contacts_deal_id_idx ON app.zillow_contacts (deal_id);
CREATE INDEX IF NOT EXISTS zillow_contacts_zillow_id_idx ON app.zillow_contacts (zillow_id);