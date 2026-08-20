import sqlite3

DB_NAME = "products.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Products Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT NOT NULL,
            stock INTEGER DEFAULT 10,
            image_url TEXT
        )
    """)

    # Orders Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_phone TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            total_price REAL NOT NULL,
            delivery_address TEXT NOT NULL,
            status TEXT DEFAULT 'pending_payment'
        )
    """)
    
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        default_products = [
            ("Wireless Bluetooth Earbuds", 2500, "Colors: Black, White.", 15, "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=800"),
            ("Smart Fitness Watch", 4500, "Tracks heart rate, steps.", 8, "https://images.unsplash.com/photo-1579586337278-3befd40fd17a?w=800"),
            ("20,000mAh Power Bank", 3200, "Fast charging, dual USB.", 20, "https://images.unsplash.com/photo-1609592424109-dd9892f1b177?w=800")
        ]
        cursor.executemany("""
            INSERT INTO products (name, price, description, stock, image_url)
            VALUES (?, ?, ?, ?, ?)
        """, default_products)
        conn.commit()
        
    conn.close()

def get_formatted_catalog() -> str:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, description, stock, image_url FROM products WHERE stock > 0")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return "No products currently in stock."
        
    catalog_lines = []
    for item in rows:
        p_id, name, price, desc, stock, img = item
        catalog_lines.append(f"ID {p_id}: {name} - KSh {price:,.0f} ({desc}) [Image Available: {img}]")
        
    return "\n".join(catalog_lines)

def create_order(customer_phone: str, product_id: int, quantity: int, address: str) -> dict:
    """Calculates total price, records order in DB, and reduces stock."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT name, price, stock FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()

    if not product or product[2] < quantity:
        conn.close()
        return {"success": False, "reason": "Insufficient stock or invalid product"}

    product_name, unit_price, current_stock = product
    total_price = unit_price * quantity

    # Insert Order
    cursor.execute("""
        INSERT INTO orders (customer_phone, product_id, quantity, total_price, delivery_address)
        VALUES (?, ?, ?, ?, ?)
    """, (customer_phone, product_id, quantity, total_price, address))
    
    order_id = cursor.lastrowid

    # Deduct Stock
    cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (quantity, product_id))
    
    conn.commit()
    conn.close()

    return {
        "success": True,
        "order_id": order_id,
        "product_name": product_name,
        "total_price": total_price,
        "address": address
    }

init_db()

import sqlite3

DB_PATH = "products.db"

def save_payment_reference(order_id: int, reference: str):
    """Saves Paystack reference to an order in products.db."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE orders SET paystack_ref = ?, payment_status = 'PENDING' WHERE id = ?",
        (reference, order_id)
    )
    conn.commit()
    conn.close()

def mark_order_as_paid(reference: str):
    """Updates order status to PAID upon receiving Paystack webhook success."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE orders SET payment_status = 'PAID' WHERE paystack_ref = ?",
        (reference,)
    )
    conn.commit()
    conn.close()

def get_all_orders():
    """Fetches all orders, standardizing the phone key for the template."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Using SELECT * avoids hardcoded column name mismatches
    cursor.execute("SELECT * FROM orders ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    orders = []
    for row in rows:
        order_dict = dict(row)
        # Standardize phone number key regardless of whether column is named 'phone' or 'phone_number'
        order_dict['phone_number'] = order_dict.get('phone_number') or order_dict.get('phone', 'N/A')
        orders.append(order_dict)

    return orders

def get_all_products():
    """Fetches all store products, automatically ensuring required columns exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check table info to see if 'is_active' exists
    cursor.execute("PRAGMA table_info(products)")
    columns = [col[1] for col in cursor.fetchall()]

    # If is_active is missing from an old database table, add it on the fly
    if "is_active" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN is_active INTEGER DEFAULT 1")
        conn.commit()

    cursor.execute("SELECT * FROM products")
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return products
def add_product(name: str, price: float, description: str = "", image_url: str = ""):
    """Inserts a new product into the database catalog."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO products (name, price, description, image_url, is_active) VALUES (?, ?, ?, ?, 1)",
        (name, price, description, image_url)
    )
    conn.commit()
    conn.close()



#leads recording
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Create leads table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_type TEXT,
            sender TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_lead(lead_type: str, sender: str, details: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO leads (lead_type, sender, details) VALUES (?, ?, ?)",
        (lead_type, sender, details)
    )
    conn.commit()
    conn.close()

def get_all_leads():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT lead_type, sender, details, created_at FROM leads ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [{"type": r[0], "sender": r[1], "details": r[2], "date": r[3]} for r in rows]