from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

DB_PATH = Path(__file__).parent / "pro_distributor.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def fetch_all(query: str, params: Iterable[Any] = ()) -> list[dict]:
    with get_conn() as conn:
        return [dict(row) for row in conn.execute(query, tuple(params)).fetchall()]


def fetch_one(query: str, params: Iterable[Any] = ()) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(query, tuple(params)).fetchone()
        return dict(row) if row else None


def execute(query: str, params: Iterable[Any] = ()) -> int:
    with get_conn() as conn:
        cur = conn.execute(query, tuple(params))
        return cur.lastrowid


def add_log(user_name: str, role: str, module: str, action: str, details: str = "") -> None:
    execute(
        """
        INSERT INTO activity_logs (log_time, user_name, role, module, action, details)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (datetime.now().isoformat(timespec="seconds"), user_name, role, module, action, details),
    )


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                mobile TEXT,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_code TEXT UNIQUE NOT NULL,
                supplier_name TEXT NOT NULL,
                contact_person TEXT,
                mobile TEXT,
                gstin TEXT,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_code TEXT UNIQUE NOT NULL,
                category_name TEXT NOT NULL,
                supplier_id INTEGER,
                active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
            );

            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_code TEXT UNIQUE NOT NULL,
                customer_name TEXT NOT NULL,
                mobile TEXT,
                email TEXT,
                gstin TEXT,
                address TEXT,
                state TEXT,
                route TEXT,
                outlet_type TEXT,
                credit_days INTEGER DEFAULT 0,
                credit_limit REAL DEFAULT 0,
                opening_balance REAL DEFAULT 0,
                cash_discount_applicable INTEGER NOT NULL DEFAULT 0,
                cash_discount_percent REAL NOT NULL DEFAULT 0,
                cash_discount_from TEXT,
                cash_discount_to TEXT,
                cash_discount_notes TEXT,
                login_enabled INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS customer_suppliers (
                customer_id INTEGER NOT NULL,
                supplier_id INTEGER NOT NULL,
                PRIMARY KEY (customer_id, supplier_id),
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
            );

            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_code TEXT UNIQUE NOT NULL,
                item_name TEXT NOT NULL,
                supplier_id INTEGER,
                category_id INTEGER,
                pcs_per_case INTEGER NOT NULL DEFAULT 1,
                stock_cases INTEGER NOT NULL DEFAULT 0,
                stock_pieces INTEGER NOT NULL DEFAULT 0,
                min_stock_cases INTEGER NOT NULL DEFAULT 0,
                mrp REAL NOT NULL DEFAULT 0,
                selling_price REAL NOT NULL DEFAULT 0,
                selling_gst_type TEXT NOT NULL DEFAULT 'Exclusive',
                purchase_price REAL NOT NULL DEFAULT 0,
                purchase_gst_type TEXT NOT NULL DEFAULT 'Exclusive',
                gst_percent REAL NOT NULL DEFAULT 0,
                hsn_code TEXT,
                barcode TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
                FOREIGN KEY (category_id) REFERENCES categories(id)
            );

            CREATE TABLE IF NOT EXISTS credit_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                credit_note_no TEXT UNIQUE NOT NULL,
                customer_id INTEGER NOT NULL,
                note_date TEXT NOT NULL,
                original_amount REAL NOT NULL,
                used_amount REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Open',
                reason TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );

            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_no TEXT UNIQUE NOT NULL,
                invoice_date TEXT NOT NULL,
                customer_id INTEGER NOT NULL,
                supplier_id INTEGER,
                salesman TEXT,
                gross_value REAL NOT NULL DEFAULT 0,
                scheme_discount REAL NOT NULL DEFAULT 0,
                cash_discount_percent REAL NOT NULL DEFAULT 0,
                cash_discount_amount REAL NOT NULL DEFAULT 0,
                taxable_amount REAL NOT NULL DEFAULT 0,
                gst_amount REAL NOT NULL DEFAULT 0,
                round_off REAL NOT NULL DEFAULT 0,
                net_amount REAL NOT NULL DEFAULT 0,
                credit_note_id INTEGER,
                credit_note_applied REAL NOT NULL DEFAULT 0,
                final_payable REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Saved',
                created_by TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
                FOREIGN KEY (credit_note_id) REFERENCES credit_notes(id)
            );

            CREATE TABLE IF NOT EXISTS invoice_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                cases_qty INTEGER NOT NULL DEFAULT 0,
                pieces_qty INTEGER NOT NULL DEFAULT 0,
                total_pieces INTEGER NOT NULL DEFAULT 0,
                rate REAL NOT NULL DEFAULT 0,
                gst_percent REAL NOT NULL DEFAULT 0,
                gross_amount REAL NOT NULL DEFAULT 0,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id),
                FOREIGN KEY (item_id) REFERENCES items(id)
            );

            CREATE TABLE IF NOT EXISTS online_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_no TEXT UNIQUE NOT NULL,
                order_date TEXT NOT NULL,
                customer_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                supplier_id INTEGER,
                total_amount REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Pending Confirmation',
                notes TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
            );

            CREATE TABLE IF NOT EXISTS collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_no TEXT UNIQUE NOT NULL,
                collection_date TEXT NOT NULL,
                customer_id INTEGER NOT NULL,
                invoice_id INTEGER,
                amount REAL NOT NULL,
                payment_mode TEXT NOT NULL,
                reference_no TEXT,
                collector TEXT,
                status TEXT NOT NULL DEFAULT 'Submitted',
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (invoice_id) REFERENCES invoices(id)
            );

            CREATE TABLE IF NOT EXISTS deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                delivery_person TEXT,
                route TEXT,
                delivery_date TEXT,
                status TEXT NOT NULL DEFAULT 'Pending Delivery',
                reason TEXT,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id)
            );

            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_time TEXT NOT NULL,
                user_name TEXT,
                role TEXT,
                module TEXT,
                action TEXT,
                details TEXT
            );
            """
        )
    seed_demo_data()


def next_number(prefix: str, table: str, column: str) -> str:
    row = fetch_one(f"SELECT COUNT(*) AS count_value FROM {table}")
    next_id = int(row["count_value"]) + 1 if row else 1
    return f"{prefix}-{date.today().year}-{next_id:04d}"


def seed_demo_data() -> None:
    if fetch_one("SELECT id FROM suppliers LIMIT 1"):
        return

    suppliers = [
        ("SUP-001", "Pidilite", "Kiran", "9000000001", "37ABCDE1234F1Z5"),
        ("SUP-002", "Asian Paints", "Ravi", "9000000002", "37ABCDE1234F1Z6"),
    ]
    for values in suppliers:
        execute(
            "INSERT INTO suppliers (supplier_code, supplier_name, contact_person, mobile, gstin) VALUES (?, ?, ?, ?, ?)",
            values,
        )

    pidilite = fetch_one("SELECT id FROM suppliers WHERE supplier_code = 'SUP-001'")["id"]
    asian = fetch_one("SELECT id FROM suppliers WHERE supplier_code = 'SUP-002'")["id"]

    categories = [
        ("CAT-001", "Adhesives", pidilite),
        ("CAT-002", "Tapes", pidilite),
        ("CAT-003", "Paints", asian),
    ]
    for values in categories:
        execute("INSERT INTO categories (category_code, category_name, supplier_id) VALUES (?, ?, ?)", values)

    adhesive = fetch_one("SELECT id FROM categories WHERE category_code = 'CAT-001'")["id"]
    tapes = fetch_one("SELECT id FROM categories WHERE category_code = 'CAT-002'")["id"]
    paints = fetch_one("SELECT id FROM categories WHERE category_code = 'CAT-003'")["id"]

    items = [
        ("ITM-001", "Fevicol 1 KG", pidilite, adhesive, 12, 15, 8, 2, 320, 280, "Exclusive", 230, "Exclusive", 18, "35069190", "890100000001"),
        ("ITM-002", "Fevibond 50 GM", pidilite, adhesive, 24, 10, 15, 2, 50, 42, "Exclusive", 34, "Exclusive", 18, "35069190", "890100000002"),
        ("ITM-003", "Masking Tape 2 Inch", pidilite, tapes, 48, 7, 12, 1, 85, 68, "Inclusive", 54, "Exclusive", 18, "39191010", "890100000003"),
        ("ITM-004", "Apcolite White 1L", asian, paints, 6, 12, 2, 2, 560, 480, "Exclusive", 400, "Exclusive", 18, "32091010", "890100000004"),
    ]
    for values in items:
        execute(
            """
            INSERT INTO items (
                item_code, item_name, supplier_id, category_id, pcs_per_case,
                stock_cases, stock_pieces, min_stock_cases, mrp, selling_price,
                selling_gst_type, purchase_price, purchase_gst_type, gst_percent,
                hsn_code, barcode
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )

    customers = [
        (
            "CUST-0041", "Sri Lakshmi Stores", "9000001001", "lakshmi@example.com", "37ABCDE1234F1Z5",
            "Nellore Main Road", "Andhra Pradesh", "NLR-04", "Retailer", 15, 50000, 0,
            1, 2.0, "2026-01-01", None, "Cash discount for eligible invoices", 1
        ),
        (
            "CUST-0042", "Venkatesh Traders", "9000001002", "venkatesh@example.com", "37ABCDE1234F1Z6",
            "Stonehousepet", "Andhra Pradesh", "NLR-04", "Wholesaler", 30, 80000, 0,
            0, 0.0, None, None, "", 1
        ),
    ]
    for values in customers:
        execute(
            """
            INSERT INTO customers (
              customer_code, customer_name, mobile, email, gstin, address, state, route,
              outlet_type, credit_days, credit_limit, opening_balance,
              cash_discount_applicable, cash_discount_percent, cash_discount_from,
              cash_discount_to, cash_discount_notes, login_enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )

    lakshmi = fetch_one("SELECT id FROM customers WHERE customer_code='CUST-0041'")["id"]
    venkatesh = fetch_one("SELECT id FROM customers WHERE customer_code='CUST-0042'")["id"]

    for cust_id, sup_id in [(lakshmi, pidilite), (lakshmi, asian), (venkatesh, pidilite)]:
        execute("INSERT INTO customer_suppliers (customer_id, supplier_id) VALUES (?, ?)", (cust_id, sup_id))

    execute(
        """
        INSERT INTO credit_notes (credit_note_no, customer_id, note_date, original_amount, used_amount, status, reason)
        VALUES ('CN-2026-0001', ?, ?, 1000, 0, 'Open', 'Sales return adjustment')
        """,
        (lakshmi, date.today().isoformat()),
    )

    users = [
        ("Administrator", "Admin", "9000002001"),
        ("Office Staff", "Staff", "9000002002"),
        ("Sri Lakshmi Stores", "Customer", "9000001001"),
        ("Ramesh Kumar", "Salesman", "9000002003"),
        ("Suresh Delivery", "Delivery", "9000002004"),
    ]
    for values in users:
        execute("INSERT INTO users (name, role, mobile) VALUES (?, ?, ?)", values)

    add_log("System", "Admin", "Setup", "Seed data created", "Demo data initialized.")


def customer_outstanding(customer_id: int) -> float:
    invoices = fetch_one(
        "SELECT COALESCE(SUM(final_payable), 0) AS total FROM invoices WHERE customer_id = ? AND status != 'Cancelled'",
        (customer_id,),
    )
    collections = fetch_one(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM collections WHERE customer_id = ? AND status = 'Approved'",
        (customer_id,),
    )
    return float(invoices["total"] or 0) - float(collections["total"] or 0)


def available_credit_notes(customer_id: int) -> list[dict]:
    return fetch_all(
        """
        SELECT id, credit_note_no, note_date, original_amount, used_amount,
               (original_amount - used_amount) AS available_amount, status, reason
        FROM credit_notes
        WHERE customer_id = ?
          AND status IN ('Open', 'Partially Used')
          AND (original_amount - used_amount) > 0
        ORDER BY note_date, id
        """,
        (customer_id,),
    )


def available_stock_pieces(item: dict) -> int:
    return int(item["stock_cases"]) * int(item["pcs_per_case"]) + int(item["stock_pieces"])


def split_pieces(total_pieces: int, pcs_per_case: int) -> tuple[int, int]:
    return divmod(max(0, int(total_pieces)), max(1, int(pcs_per_case)))


def update_stock_after_sale(item_id: int, total_pieces: int) -> None:
    item = fetch_one("SELECT * FROM items WHERE id = ?", (item_id,))
    if not item:
        raise ValueError("Item not found.")
    remaining = available_stock_pieces(item) - int(total_pieces)
    if remaining < 0:
        raise ValueError(f"Not enough stock for {item['item_name']}.")
    cases, pieces = split_pieces(remaining, item["pcs_per_case"])
    execute("UPDATE items SET stock_cases = ?, stock_pieces = ? WHERE id = ?", (cases, pieces, item_id))


def create_invoice(payload: dict, lines: list[dict]) -> int:
    if not lines:
        raise ValueError("Add at least one item before saving invoice.")

    invoice_no = next_number("INV", "invoices", "invoice_no")
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO invoices (
              invoice_no, invoice_date, customer_id, supplier_id, salesman,
              gross_value, scheme_discount, cash_discount_percent, cash_discount_amount,
              taxable_amount, gst_amount, round_off, net_amount, credit_note_id,
              credit_note_applied, final_payable, status, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invoice_no, payload["invoice_date"], payload["customer_id"], payload.get("supplier_id"),
                payload.get("salesman", ""), payload["gross_value"], payload["scheme_discount"],
                payload["cash_discount_percent"], payload["cash_discount_amount"], payload["taxable_amount"],
                payload["gst_amount"], payload["round_off"], payload["net_amount"],
                payload.get("credit_note_id"), payload["credit_note_applied"],
                payload["final_payable"], "Saved", payload["created_by"],
            ),
        )
        invoice_id = cur.lastrowid

        for line in lines:
            item = conn.execute("SELECT * FROM items WHERE id = ?", (line["item_id"],)).fetchone()
            if not item:
                raise ValueError("Item not found while saving.")
            available = int(item["stock_cases"]) * int(item["pcs_per_case"]) + int(item["stock_pieces"])
            if line["total_pieces"] > available:
                raise ValueError(f"Insufficient stock for {item['item_name']}.")

            conn.execute(
                """
                INSERT INTO invoice_lines (
                    invoice_id, item_id, cases_qty, pieces_qty, total_pieces,
                    rate, gst_percent, gross_amount
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_id, line["item_id"], line["cases_qty"], line["pieces_qty"],
                    line["total_pieces"], line["rate"], line["gst_percent"], line["gross_amount"],
                ),
            )
            remaining = available - int(line["total_pieces"])
            cases, pieces = split_pieces(remaining, int(item["pcs_per_case"]))
            conn.execute(
                "UPDATE items SET stock_cases = ?, stock_pieces = ? WHERE id = ?",
                (cases, pieces, line["item_id"]),
            )

        if payload.get("credit_note_id") and payload["credit_note_applied"] > 0:
            cn = conn.execute("SELECT * FROM credit_notes WHERE id = ?", (payload["credit_note_id"],)).fetchone()
            if not cn:
                raise ValueError("Credit note not found.")
            available_credit = float(cn["original_amount"]) - float(cn["used_amount"])
            if payload["credit_note_applied"] > available_credit:
                raise ValueError("Credit note amount exceeds its available balance.")
            new_used = float(cn["used_amount"]) + float(payload["credit_note_applied"])
            new_status = "Used" if new_used >= float(cn["original_amount"]) else "Partially Used"
            conn.execute(
                "UPDATE credit_notes SET used_amount = ?, status = ? WHERE id = ?",
                (new_used, new_status, payload["credit_note_id"]),
            )

        customer = conn.execute("SELECT route FROM customers WHERE id = ?", (payload["customer_id"],)).fetchone()
        conn.execute(
            """
            INSERT INTO deliveries (invoice_id, delivery_person, route, delivery_date, status)
            VALUES (?, ?, ?, ?, 'Pending Delivery')
            """,
            (invoice_id, "", customer["route"] if customer else "", payload["invoice_date"]),
        )

        conn.execute(
            """
            INSERT INTO activity_logs (log_time, user_name, role, module, action, details)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(timespec="seconds"), payload["created_by"], payload["role"],
                "Sales", "Invoice Created", f"{invoice_no} | Final Payable: {payload['final_payable']:.2f}",
            ),
        )
    return invoice_id
