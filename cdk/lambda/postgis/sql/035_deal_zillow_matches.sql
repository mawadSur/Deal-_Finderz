-- Table for storing Zillow matches for deals
CREATE TABLE IF NOT EXISTS app.deal_zillow_matches (
    id BIGSERIAL PRIMARY KEY,
    deal_id BIGINT NOT NULL REFERENCES app.deals(id) ON DELETE CASCADE,
    zillow_id TEXT NOT NULL,
    match_score NUMERIC(3,2) NOT NULL CHECK (match_score >= 0 AND match_score <= 1),
    distance_meters NUMERIC(10,2),
    price_diff_percent NUMERIC(5,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS deal_zillow_matches_deal_id_idx ON app.deal_zillow_matches (deal_id);
CREATE INDEX IF NOT EXISTS deal_zillow_matches_zillow_id_idx ON app.deal_zillow_matches (zillow_id);
CREATE INDEX IF NOT EXISTS deal_zillow_matches_score_idx ON app.deal_zillow_matches (match_score DESC);