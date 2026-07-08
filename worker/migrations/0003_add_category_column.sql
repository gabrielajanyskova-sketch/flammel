-- Lets Gabriela pick a category for a product directly in the same
-- product_stock table, alongside price/stock — see migrations 0002 for
-- why this is a separate file (ALTER TABLE isn't safely re-runnable).
ALTER TABLE product_stock ADD COLUMN category_slug TEXT;
