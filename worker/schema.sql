CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_number TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL DEFAULT 'nova',
  customer_name TEXT NOT NULL,
  customer_email TEXT NOT NULL,
  customer_phone TEXT,
  delivery_method TEXT NOT NULL,
  delivery_detail TEXT,
  billing_detail TEXT,
  payment_method TEXT NOT NULL,
  note TEXT,
  subtotal INTEGER NOT NULL,
  shipping_price INTEGER NOT NULL,
  payment_fee INTEGER NOT NULL,
  total INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS order_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL REFERENCES orders(id),
  product_id TEXT NOT NULL,
  title TEXT NOT NULL,
  price INTEGER NOT NULL,
  qty INTEGER NOT NULL
);
