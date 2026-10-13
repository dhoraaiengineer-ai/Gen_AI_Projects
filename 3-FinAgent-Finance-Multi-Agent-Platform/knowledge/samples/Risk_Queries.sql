-- Risk queries used by the daily risk report (read-only).
-- Portfolio weights by sector.
SELECT p.code, i.sector, SUM(h.quantity * m.close) AS value
FROM holdings h JOIN portfolios p ON p.id = h.portfolio_id
JOIN instruments i ON i.id = h.instrument_id
JOIN market_data m ON m.instrument_id = i.id AND m.trade_date = :as_of
GROUP BY p.code, i.sector;

-- Positions above the 20% warning threshold.
SELECT p.code, i.ticker, h.quantity
FROM holdings h JOIN portfolios p ON p.id = h.portfolio_id
JOIN instruments i ON i.id = h.instrument_id
WHERE h.weight > 0.20;
