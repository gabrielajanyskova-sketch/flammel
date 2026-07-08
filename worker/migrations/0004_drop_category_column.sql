-- Reverts 0003 — a dropdown-free raw D1 table turned out to be more
-- confusing than helpful for picking a category, so category changes go
-- back to being made directly in code/content instead.
ALTER TABLE product_stock DROP COLUMN category_slug;
