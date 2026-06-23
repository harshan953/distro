# Pro Distributor — Simple Streamlit App

This is a simple editable Streamlit implementation of the Pro Distributor workflow.

## Included working modules

- Role-based navigation: Admin, Staff, Customer, Salesman, Delivery
- Customer Master with **Cash Discount Applicable** and **Cash Discount %**
- Supplier / Distribution Company Master
- Categories and Item Master
- Customer Company allocation
- Catalog and Cart
- Online Orders
- Sales Billing
- Customer-level Cash Discount auto-loading in Billing
- Scheme Discount input
- GST calculation
- Nearest Rupee Round-off:
  - Below ₹0.50 rounds down
  - ₹0.50 and above rounds up
- Same-Customer Credit Note selection and partial usage
- Invoice save:
  - Saves invoice
  - Reduces stock
  - Updates Credit Note used balance
  - Creates Pending Delivery
  - Adds Activity Log
- Payment Collections with Admin approval
- Day Cash Closing with denominations
- Delivery Status updates
- Routes / GPS demo controls
- Reports and CSV export
- Activity Log
- SQLite database with sample data

## Important invoice formula

```text
Gross Value
− Scheme Discount
− Cash Discount
= Taxable Amount

Taxable Amount
+ GST Amount
= Subtotal

Subtotal
± Round Off
= Net Amount

Net Amount
− Applied Same-Customer Credit Note
= Final Payable Amount
```

## Install and run

Open Terminal / Command Prompt inside this project folder:

```bash
python -m venv .venv
```

### Windows

```bash
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

### macOS / Linux

```bash
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Then open the address shown in Terminal, usually:

```text
http://localhost:8501
```

## Editable files

- `app.py` — all pages, Streamlit user interface, and role menus.
- `database.py` — SQLite tables, sample data, invoice save logic, stock update logic.
- `pro_distributor.db` — generated automatically after first run; this contains your data.

## Where to change common things

### Add a new field to Customer Master

1. Add the database column inside `customers` table in `database.py`.
2. Add the Streamlit input inside `render_masters()` in `app.py`.
3. Add it to the Customer `INSERT` query.
4. Use it in Billing if needed.

### Change Invoice Formula

Edit `render_sales_billing()` in `app.py`.

### Change round-off behavior

Edit `nearest_rupee()` in `app.py`.

### Add new roles or permissions

Edit `role_menu` and `can_edit_billing()` / `can_approve()` in `app.py`.

## Notes

This is intentionally a simple Streamlit build. It uses local SQLite, which is good for learning, prototyping, and one-office usage.

For a future production version with true mobile offline PWA, background GPS, push notifications, many simultaneous users, and stronger security, migrate the same business logic to React + Node.js + PostgreSQL.
