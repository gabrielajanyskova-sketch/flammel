-- Adds price columns to product_stock so Gabriela can manage price + stock
-- for products in one place (Cloudflare dashboard), without needing a code
-- change per product. Run individually (not part of schema.sql) because
-- ALTER TABLE ADD COLUMN isn't safely re-runnable — the deploy workflow
-- tolerates "duplicate column" on repeat runs.
ALTER TABLE product_stock ADD COLUMN regular_price INTEGER;
ALTER TABLE product_stock ADD COLUMN sale_price INTEGER;
