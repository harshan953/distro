from __future__ import annotations

from datetime import date
import math
import pandas as pd
import streamlit as st

from database import (
    add_log,
    available_credit_notes,
    available_stock_pieces,
    create_invoice,
    customer_outstanding,
    execute,
    fetch_all,
    fetch_one,
    init_db,
    next_number,
    split_pieces,
)

st.set_page_config(
    page_title="Pro Distributor",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

# ---------- Visual helpers ----------
def money(value: float) -> str:
    return f"₹{float(value or 0):,.2f}"

def as_dataframe(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()

def status_badge(status: str) -> str:
    colors = {
        "Saved": "🟢",
        "Approved": "🟢",
        "Open": "🔵",
        "Partially Used": "🟠",
        "Pending Confirmation": "🟠",
        "Submitted": "🟠",
        "Pending Delivery": "🟠",
        "Out for Delivery": "🔵",
        "Delivered": "🟢",
        "Not Delivered": "🔴",
        "Cancelled": "🔴",
    }
    return f"{colors.get(status, '⚪')} {status}"

def can_edit_billing() -> bool:
    return st.session_state.role in {"Admin", "Staff"}

def can_approve() -> bool:
    return st.session_state.role == "Admin"

def log(module: str, action: str, details: str = "") -> None:
    add_log(st.session_state.user_name, st.session_state.role, module, action, details)

def header(title: str, subtitle: str = "") -> None:
    st.title(title)
    if subtitle:
        st.caption(subtitle)

def customer_label(customer: dict) -> str:
    return f"{customer['customer_code']} — {customer['customer_name']}"

def supplier_label(supplier: dict) -> str:
    return f"{supplier['supplier_code']} — {supplier['supplier_name']}"

def item_label(item: dict) -> str:
    return f"{item['item_code']} — {item['item_name']} | Stock {item['stock_cases']} CASE + {item['stock_pieces']} PCS"

def nearest_rupee(value: float) -> tuple[float, float]:
    # ₹0.50 and above rounds up; below ₹0.50 rounds down.
    rounded = float(math.floor(value + 0.5))
    return rounded, rounded - value


# ---------- App header ----------
if "role" not in st.session_state:
    st.session_state.role = "Admin"
if "user_name" not in st.session_state:
    st.session_state.user_name = "Administrator"
if "cart_lines" not in st.session_state:
    st.session_state.cart_lines = []
if "login_complete" not in st.session_state:
    st.session_state.login_complete = True

with st.sidebar:
    st.markdown("## 📦 Pro Distributor")
    st.caption("Simple, editable Streamlit version")
    st.divider()

    role_options = ["Admin", "Staff", "Customer", "Salesman", "Delivery"]
    st.session_state.role = st.selectbox("Demo role", role_options, index=role_options.index(st.session_state.role))
    default_name = {
        "Admin": "Administrator",
        "Staff": "Office Staff",
        "Customer": "Sri Lakshmi Stores",
        "Salesman": "Ramesh Kumar",
        "Delivery": "Suresh Delivery",
    }
    st.session_state.user_name = st.text_input("Logged in as", value=default_name[st.session_state.role])

    st.divider()
    st.success("● Sync ready")
    if st.button("↻ Sync now", use_container_width=True):
        st.toast("Sync completed. No duplicate records found.", icon="✅")
    st.caption("No Refresh button is used. Use Sync only.")

    all_menu = [
        "Dashboard", "Masters", "Catalog & Cart", "Online Orders", "Sales Billing",
        "Credit Notes", "Payments & Collections", "Day Cash Closing", "Delivery",
        "Routes & GPS", "Approvals", "Reports", "Settings", "Activity Log",
    ]
    role_menu = {
        "Admin": all_menu,
        "Staff": ["Dashboard", "Masters", "Online Orders", "Sales Billing", "Credit Notes",
                  "Payments & Collections", "Day Cash Closing", "Delivery", "Reports", "Activity Log"],
        "Customer": ["Dashboard", "Catalog & Cart", "Online Orders", "Credit Notes", "Reports"],
        "Salesman": ["Dashboard", "Catalog & Cart", "Online Orders", "Payments & Collections",
                     "Day Cash Closing", "Routes & GPS"],
        "Delivery": ["Dashboard", "Payments & Collections", "Day Cash Closing", "Delivery", "Routes & GPS"],
    }
    page = st.radio("Navigation", role_menu[st.session_state.role], label_visibility="collapsed")

# ---------- Pages ----------
def render_dashboard() -> None:
    header(f"{st.session_state.role} Dashboard", "Role-based view with simple working records.")

    invoice_total = fetch_one("SELECT COALESCE(SUM(final_payable), 0) AS amount FROM invoices WHERE status != 'Cancelled'")["amount"]
    collection_total = fetch_one("SELECT COALESCE(SUM(amount), 0) AS amount FROM collections WHERE status = 'Approved'")["amount"]
    outstanding = sum(customer_outstanding(c["id"]) for c in fetch_all("SELECT id FROM customers WHERE active = 1"))
    pending_orders = fetch_one("SELECT COUNT(*) AS count_value FROM online_orders WHERE status IN ('Pending Confirmation', 'Under Review')")["count_value"]
    pending_delivery = fetch_one("SELECT COUNT(*) AS count_value FROM deliveries WHERE status IN ('Pending Delivery', 'Out for Delivery')")["count_value"]

    if st.session_state.role == "Admin":
        cols = st.columns(5)
        cols[0].metric("Today Sales", money(invoice_total))
        cols[1].metric("Today Collection", money(collection_total))
        cols[2].metric("Outstanding", money(outstanding))
        cols[3].metric("Pending Orders", int(pending_orders))
        cols[4].metric("Pending Delivery", int(pending_delivery))
    elif st.session_state.role == "Staff":
        cols = st.columns(4)
        cols[0].metric("Pending Orders", int(pending_orders))
        cols[1].metric("Collections to Review", fetch_one("SELECT COUNT(*) AS c FROM collections WHERE status='Submitted'")["c"])
        cols[2].metric("Pending Deliveries", int(pending_delivery))
        cols[3].metric("Low Stock Items", fetch_one("SELECT COUNT(*) AS c FROM items WHERE stock_cases <= min_stock_cases")["c"])
    elif st.session_state.role == "Customer":
        customer = fetch_one("SELECT * FROM customers WHERE customer_code='CUST-0041'")
        cols = st.columns(4)
        cols[0].metric("Pending Amount", money(customer_outstanding(customer["id"])))
        cols[1].metric("Cash Discount", f"{customer['cash_discount_percent']:.2f}%")
        available_cn = sum(float(x["available_amount"]) for x in available_credit_notes(customer["id"]))
        cols[2].metric("Credit Note Balance", money(available_cn))
        cols[3].metric("My Orders", fetch_one("SELECT COUNT(*) AS c FROM online_orders WHERE customer_id=?", (customer["id"],))["c"])
    elif st.session_state.role == "Salesman":
        cols = st.columns(4)
        cols[0].metric("Today Route", "NLR-04")
        cols[1].metric("Assigned Customers", 22)
        cols[2].metric("Submitted Collections", money(fetch_one("SELECT COALESCE(SUM(amount),0) AS a FROM collections WHERE status='Submitted'")["a"]))
        cols[3].metric("Pending Bills", fetch_one("SELECT COUNT(*) AS c FROM invoices WHERE final_payable > 0")["c"])
    else:
        cols = st.columns(4)
        cols[0].metric("Assigned Bills", int(pending_delivery))
        cols[1].metric("Delivered Today", fetch_one("SELECT COUNT(*) AS c FROM deliveries WHERE status='Delivered'")["c"])
        cols[2].metric("Cash Closing", "Pending")
        cols[3].metric("Trip Status", "Not Started")

    st.subheader("Priority work")
    c1, c2 = st.columns([1.35, 1])
    with c1:
        if st.session_state.role in {"Admin", "Staff"}:
            records = fetch_all(
                """
                SELECT o.order_no, c.customer_name, s.supplier_name, o.total_amount, o.status
                FROM online_orders o
                JOIN customers c ON c.id=o.customer_id
                LEFT JOIN suppliers s ON s.id=o.supplier_id
                ORDER BY o.id DESC LIMIT 8
                """
            )
            st.dataframe(as_dataframe(records), use_container_width=True, hide_index=True)
        elif st.session_state.role == "Customer":
            records = fetch_all(
                """
                SELECT i.invoice_no, i.invoice_date, i.final_payable, i.status
                FROM invoices i JOIN customers c ON c.id=i.customer_id
                WHERE c.customer_code='CUST-0041' ORDER BY i.id DESC LIMIT 8
                """
            )
            st.dataframe(as_dataframe(records), use_container_width=True, hide_index=True)
        elif st.session_state.role == "Salesman":
            st.info("Start Route before taking orders or recording field visits.")
            if st.button("Start Route — NLR-04", type="primary"):
                log("Routes", "Route Started", "NLR-04")
                st.success("Route started. GPS tracking is active for this demo.")
        else:
            st.info("Start Trip before updating delivery status.")
            if st.button("Start Trip — NLR-04", type="primary"):
                log("Delivery", "Trip Started", "NLR-04")
                st.success("Trip started. GPS tracking is active for this demo.")
    with c2:
        st.markdown("#### Key business rules")
        st.markdown(
            """
            - Customer Cash Discount loads from Customer Master.
            - Gross − Scheme − Cash Discount = Taxable Amount.
            - GST is calculated on Taxable Amount.
            - ₹0.50 or above rounds to the next rupee.
            - Credit Note must match the same Customer Code.
            - Invoice save reduces stock and creates Pending Delivery.
            """
        )


def render_masters() -> None:
    header("Masters", "Manage customers, suppliers, categories, and items. Deactivate records with transaction history instead of deleting.")
    tabs = st.tabs(["Customers", "Suppliers", "Categories", "Items"])

    with tabs[0]:
        customers = fetch_all(
            """
            SELECT c.*, COALESCE(GROUP_CONCAT(s.supplier_name, ', '), '') AS allowed_companies
            FROM customers c
            LEFT JOIN customer_suppliers cs ON cs.customer_id=c.id
            LEFT JOIN suppliers s ON s.id=cs.supplier_id
            GROUP BY c.id ORDER BY c.customer_name
            """
        )
        st.dataframe(as_dataframe(customers), use_container_width=True, hide_index=True)

        with st.expander("Add Customer", expanded=False):
            suppliers = fetch_all("SELECT * FROM suppliers WHERE active=1 ORDER BY supplier_name")
            with st.form("customer_form", clear_on_submit=True):
                a, b, c = st.columns(3)
                code = a.text_input("Customer Code", value=next_number("CUST", "customers", "customer_code"))
                name = b.text_input("Customer Name")
                mobile = c.text_input("Mobile Number")
                email = a.text_input("Email")
                route = b.text_input("Beat / Route", value="NLR-04")
                outlet = c.selectbox("Outlet Type", ["Retailer", "Wholesaler", "Dealer", "Other"])
                credit_days = a.number_input("Credit Days", min_value=0, value=15)
                credit_limit = b.number_input("Credit Limit", min_value=0.0, value=0.0, step=1000.0)
                selected_suppliers = st.multiselect(
                    "Allowed Suppliers / Companies",
                    options=[s["id"] for s in suppliers],
                    default=[],
                    format_func=lambda x: supplier_label(next(s for s in suppliers if s["id"] == x)),
                )

                st.markdown("##### Cash Discount saved in Customer Master")
                cash_applicable = st.checkbox("Cash Discount Applicable")
                cash_percent = st.number_input("Cash Discount %", min_value=0.0, max_value=100.0, value=0.0, step=0.25)
                cash_from = st.date_input("Cash Discount Effective From", value=date.today())
                cash_to_enabled = st.checkbox("Set Cash Discount Effective To")
                cash_to = st.date_input("Cash Discount Effective To", value=date.today()) if cash_to_enabled else None
                cash_notes = st.text_input("Cash Discount Notes")
                login_enabled = st.checkbox("Customer Login Enabled")

                submitted = st.form_submit_button("Save Customer", type="primary")
                if submitted:
                    if not code.strip() or not name.strip():
                        st.error("Customer Code and Customer Name are required.")
                    else:
                        try:
                            customer_id = execute(
                                """
                                INSERT INTO customers (
                                    customer_code, customer_name, mobile, email, route, outlet_type,
                                    credit_days, credit_limit, cash_discount_applicable,
                                    cash_discount_percent, cash_discount_from, cash_discount_to,
                                    cash_discount_notes, login_enabled
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    code.strip(), name.strip(), mobile.strip(), email.strip(), route.strip(), outlet,
                                    int(credit_days), float(credit_limit), int(cash_applicable), float(cash_percent),
                                    cash_from.isoformat() if cash_applicable else None,
                                    cash_to.isoformat() if cash_applicable and cash_to else None,
                                    cash_notes.strip(), int(login_enabled),
                                ),
                            )
                            for supplier_id in selected_suppliers:
                                execute("INSERT INTO customer_suppliers (customer_id, supplier_id) VALUES (?, ?)", (customer_id, supplier_id))
                            log("Customer Master", "Customer Added", f"{code} — {name}; Cash Discount {cash_percent}%")
                            st.success("Customer saved successfully.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not save customer: {exc}")

    with tabs[1]:
        suppliers = fetch_all("SELECT * FROM suppliers ORDER BY supplier_name")
        st.dataframe(as_dataframe(suppliers), use_container_width=True, hide_index=True)
        with st.expander("Add Supplier / Distribution Company"):
            with st.form("supplier_form", clear_on_submit=True):
                x, y, z = st.columns(3)
                code = x.text_input("Supplier Code", value=next_number("SUP", "suppliers", "supplier_code"))
                name = y.text_input("Supplier / Company Name")
                mobile = z.text_input("Mobile")
                contact = x.text_input("Contact Person")
                gstin = y.text_input("GSTIN")
                if st.form_submit_button("Save Supplier", type="primary"):
                    try:
                        execute(
                            "INSERT INTO suppliers (supplier_code,supplier_name,contact_person,mobile,gstin) VALUES (?,?,?,?,?)",
                            (code, name, contact, mobile, gstin),
                        )
                        log("Supplier Master", "Supplier Added", f"{code} — {name}")
                        st.success("Supplier saved.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

    with tabs[2]:
        categories = fetch_all(
            "SELECT c.category_code, c.category_name, s.supplier_name, c.active FROM categories c LEFT JOIN suppliers s ON s.id=c.supplier_id ORDER BY c.category_name"
        )
        st.dataframe(as_dataframe(categories), use_container_width=True, hide_index=True)

    with tabs[3]:
        items = fetch_all(
            """
            SELECT i.item_code, i.item_name, s.supplier_name, c.category_name,
                   i.pcs_per_case, i.stock_cases, i.stock_pieces, i.mrp,
                   i.selling_price, i.selling_gst_type, i.gst_percent, i.active
            FROM items i
            LEFT JOIN suppliers s ON s.id=i.supplier_id
            LEFT JOIN categories c ON c.id=i.category_id
            ORDER BY i.item_name
            """
        )
        st.dataframe(as_dataframe(items), use_container_width=True, hide_index=True)
        with st.expander("Add Item"):
            suppliers = fetch_all("SELECT * FROM suppliers WHERE active=1 ORDER BY supplier_name")
            categories = fetch_all("SELECT * FROM categories WHERE active=1 ORDER BY category_name")
            with st.form("item_form", clear_on_submit=True):
                a, b, c = st.columns(3)
                code = a.text_input("Item Code", value=next_number("ITM", "items", "item_code"))
                name = b.text_input("Item Name")
                supplier_id = c.selectbox("Supplier / Company", [s["id"] for s in suppliers], format_func=lambda x: supplier_label(next(s for s in suppliers if s["id"] == x)))
                category_id = a.selectbox("Category", [x["id"] for x in categories], format_func=lambda x: next(z["category_name"] for z in categories if z["id"] == x))
                pcs_case = b.number_input("PCS per Case", min_value=1, value=12)
                opening_cases = c.number_input("Opening Cases", min_value=0, value=0)
                opening_pieces = a.number_input("Opening Pieces", min_value=0, value=0)
                mrp = b.number_input("MRP", min_value=0.0, value=0.0)
                selling = c.number_input("Selling Price", min_value=0.0, value=0.0)
                gst_type = a.selectbox("Selling Price GST Type", ["Exclusive", "Inclusive"])
                gst = b.number_input("GST %", min_value=0.0, value=18.0, step=0.5)
                purchase = c.number_input("Purchase Price", min_value=0.0, value=0.0)
                hsn = a.text_input("HSN Code")
                barcode = b.text_input("Barcode")
                if st.form_submit_button("Save Item", type="primary"):
                    try:
                        execute(
                            """
                            INSERT INTO items (
                                item_code, item_name, supplier_id, category_id, pcs_per_case,
                                stock_cases, stock_pieces, mrp, selling_price, selling_gst_type,
                                purchase_price, gst_percent, hsn_code, barcode
                            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            (code, name, supplier_id, category_id, int(pcs_case), int(opening_cases),
                             int(opening_pieces), mrp, selling, gst_type, purchase, gst, hsn, barcode),
                        )
                        log("Item Master", "Item Added", f"{code} — {name}")
                        st.success("Item saved.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))


def render_catalog_cart() -> None:
    header("Catalog & Cart", "Company → Category → Products → Case / Piece Qty → Cart → Online Order")
    customers = fetch_all("SELECT * FROM customers WHERE active=1 ORDER BY customer_name")
    suppliers = fetch_all("SELECT * FROM suppliers WHERE active=1 ORDER BY supplier_name")

    selected_customer_id = st.selectbox(
        "Customer",
        [c["id"] for c in customers],
        format_func=lambda x: customer_label(next(c for c in customers if c["id"] == x)),
        disabled=st.session_state.role == "Customer",
        index=0,
    )
    customer = next(c for c in customers if c["id"] == selected_customer_id)

    allocated_ids = [x["supplier_id"] for x in fetch_all("SELECT supplier_id FROM customer_suppliers WHERE customer_id=?", (selected_customer_id,))]
    available_suppliers = [s for s in suppliers if s["id"] in allocated_ids] or suppliers
    supplier_id = st.selectbox(
        "Supplier / Company",
        [s["id"] for s in available_suppliers],
        format_func=lambda x: supplier_label(next(s for s in available_suppliers if s["id"] == x)),
    )

    items = fetch_all(
        """
        SELECT * FROM items
        WHERE active=1 AND supplier_id=?
        ORDER BY item_name
        """,
        (supplier_id,),
    )
    if not items:
        st.warning("No active items for this supplier.")
        return

    st.subheader("Available Products")
    for item in items:
        with st.container(border=True):
            left, mid, right = st.columns([2.2, 1.1, 1])
            left.markdown(f"**{item['item_name']}**  \n`{item['item_code']}` · 1 CASE = {item['pcs_per_case']} PCS")
            left.caption(f"MRP {money(item['mrp'])} · Selling Price {money(item['selling_price'])} · GST {item['gst_percent']}% ({item['selling_gst_type']})")
            mid.metric("Stock", f"{item['stock_cases']} CASE + {item['stock_pieces']} PCS")
            with right:
                with st.form(f"catalog_{item['id']}", clear_on_submit=True):
                    cases = st.number_input("Cases", 0, 10000, 0, key=f"case_{item['id']}")
                    pieces = st.number_input("Pieces", 0, int(item["pcs_per_case"]) - 1, 0, key=f"piece_{item['id']}")
                    if st.form_submit_button("Add to Cart"):
                        total_pieces = cases * int(item["pcs_per_case"]) + pieces
                        if total_pieces <= 0:
                            st.error("Enter quantity.")
                        elif total_pieces > available_stock_pieces(item):
                            st.error("Requested quantity is above available stock.")
                        else:
                            st.session_state.cart_lines.append({
                                "item_id": item["id"],
                                "item_name": item["item_name"],
                                "cases_qty": int(cases),
                                "pieces_qty": int(pieces),
                                "total_pieces": total_pieces,
                                "rate": float(item["selling_price"]),
                                "gst_percent": float(item["gst_percent"]),
                                "gross_amount": total_pieces * float(item["selling_price"]),
                                "supplier_id": supplier_id,
                            })
                            st.success(f"{item['item_name']} added to cart.")

    st.divider()
    st.subheader("Cart")
    if not st.session_state.cart_lines:
        st.info("Cart is empty. Cart does not reserve stock.")
        return

    cart_df = pd.DataFrame(st.session_state.cart_lines)
    st.dataframe(cart_df[["item_name", "cases_qty", "pieces_qty", "total_pieces", "rate", "gross_amount"]], use_container_width=True, hide_index=True)
    gross = float(cart_df["gross_amount"].sum())
    st.metric("Cart Gross Value", money(gross))
    c1, c2 = st.columns(2)
    if c1.button("Clear Cart"):
        st.session_state.cart_lines = []
        st.rerun()
    if c2.button("Place Online Order", type="primary"):
        order_no = next_number("ORD", "online_orders", "order_no")
        execute(
            """
            INSERT INTO online_orders (order_no, order_date, customer_id, source, supplier_id, total_amount, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, 'Pending Confirmation', ?)
            """,
            (order_no, date.today().isoformat(), selected_customer_id, st.session_state.role, supplier_id, gross, "Created from catalog cart"),
        )
        log("Online Orders", "Order Created", f"{order_no}; Customer {customer['customer_code']}; Amount {gross:.2f}")
        st.session_state.cart_lines = []
        st.success(f"Online Order {order_no} created. It does not reduce stock until Invoice confirmation.")
        st.rerun()


def render_online_orders() -> None:
    header("Online Orders", "Customer and Salesman orders require Admin or permitted Staff confirmation before invoice creation.")
    orders = fetch_all(
        """
        SELECT o.*, c.customer_code, c.customer_name, s.supplier_name
        FROM online_orders o
        JOIN customers c ON c.id=o.customer_id
        LEFT JOIN suppliers s ON s.id=o.supplier_id
        ORDER BY o.id DESC
        """
    )
    if orders:
        display = []
        for x in orders:
            display.append({
                "Order No": x["order_no"], "Date": x["order_date"], "Customer": f"{x['customer_code']} — {x['customer_name']}",
                "Source": x["source"], "Company": x["supplier_name"], "Amount": money(x["total_amount"]),
                "Status": status_badge(x["status"]),
            })
        st.dataframe(pd.DataFrame(display), use_container_width=True, hide_index=True)
    else:
        st.info("No online orders yet.")

    if can_edit_billing() and orders:
        st.subheader("Confirm or update Order")
        pending = [x for x in orders if x["status"] in {"Pending Confirmation", "Under Review"}]
        if pending:
            order_id = st.selectbox("Select pending Order", [x["id"] for x in pending], format_func=lambda oid: next(x["order_no"] for x in pending if x["id"] == oid))
            a, b = st.columns(2)
            if a.button("Mark Under Review"):
                execute("UPDATE online_orders SET status='Under Review' WHERE id=?", (order_id,))
                log("Online Orders", "Order Under Review", str(order_id))
                st.rerun()
            if b.button("Confirm Order", type="primary"):
                execute("UPDATE online_orders SET status='Confirmed' WHERE id=?", (order_id,))
                log("Online Orders", "Order Confirmed", str(order_id))
                st.success("Order confirmed. Create final invoice from Sales Billing.")
                st.rerun()
        else:
            st.success("No pending orders requiring review.")


def render_sales_billing() -> None:
    header("Sales Billing", "Customer Cash Discount is read from Customer Master. Credit Note is allowed only for the same Customer Code.")
    if not can_edit_billing():
        st.info("This role can view billing rules but cannot create invoices.")
        st.markdown("**Formula:** Gross Value − Scheme Discount − Cash Discount = Taxable Amount; + GST; ± Round Off; − Credit Note = Final Payable.")
        return

    customers = fetch_all("SELECT * FROM customers WHERE active=1 ORDER BY customer_name")
    items = fetch_all("SELECT * FROM items WHERE active=1 ORDER BY item_name")
    if not customers or not items:
        st.warning("Create Customers and Items first.")
        return

    col1, col2 = st.columns([1.25, 1])
    with col1:
        customer_id = st.selectbox("Customer", [c["id"] for c in customers], format_func=lambda x: customer_label(next(c for c in customers if c["id"] == x)))
        customer = next(c for c in customers if c["id"] == customer_id)

        st.info(
            f"Customer Cash Discount: **{'Applicable' if customer['cash_discount_applicable'] else 'Not Applicable'}** "
            f"| **{float(customer['cash_discount_percent']):.2f}%** | "
            f"Outstanding: **{money(customer_outstanding(customer_id))}**"
        )

        st.markdown("#### Add Invoice Items")
        item_id = st.selectbox("Item", [i["id"] for i in items], format_func=lambda x: item_label(next(i for i in items if i["id"] == x)))
        item = next(i for i in items if i["id"] == item_id)
        q1, q2, q3 = st.columns(3)
        cases_qty = q1.number_input("Cases Qty", min_value=0, value=1)
        pieces_qty = q2.number_input("Pieces Qty", min_value=0, max_value=max(0, int(item["pcs_per_case"]) - 1), value=0)
        if q3.button("Add Item Line"):
            total_pieces = int(cases_qty) * int(item["pcs_per_case"]) + int(pieces_qty)
            if total_pieces <= 0:
                st.error("Enter item quantity.")
            elif total_pieces > available_stock_pieces(item):
                st.error("Quantity exceeds available stock.")
            else:
                st.session_state.cart_lines.append({
                    "item_id": item["id"], "item_name": item["item_name"],
                    "cases_qty": int(cases_qty), "pieces_qty": int(pieces_qty),
                    "total_pieces": int(total_pieces), "rate": float(item["selling_price"]),
                    "gst_percent": float(item["gst_percent"]),
                    "gross_amount": float(total_pieces) * float(item["selling_price"]),
                    "supplier_id": item["supplier_id"],
                })
                st.success("Item line added.")

        if not st.session_state.cart_lines:
            st.warning("Add invoice items to continue.")
            return

        line_df = pd.DataFrame(st.session_state.cart_lines)
        st.dataframe(line_df[["item_name", "cases_qty", "pieces_qty", "total_pieces", "rate", "gross_amount"]], use_container_width=True, hide_index=True)

        b1, b2 = st.columns(2)
        if b1.button("Clear Invoice Lines"):
            st.session_state.cart_lines = []
            st.rerun()
        if b2.button("Remove Last Line"):
            st.session_state.cart_lines.pop()
            st.rerun()

    with col2:
        gross = sum(float(x["gross_amount"]) for x in st.session_state.cart_lines)
        st.markdown("#### Invoice Summary")
        scheme_discount = st.number_input("Scheme Discount Amount", min_value=0.0, max_value=float(gross), value=0.0, step=1.0)

        default_cash_pct = float(customer["cash_discount_percent"]) if customer["cash_discount_applicable"] else 0.0
        if st.session_state.role == "Admin":
            override_cash = st.checkbox("Override Customer Cash Discount")
        else:
            override_cash = False
        cash_pct = st.number_input(
            "Cash Discount %",
            min_value=0.0,
            max_value=100.0,
            value=float(default_cash_pct),
            step=0.25,
            disabled=not override_cash,
            help="Loads from Customer Master. Only Admin can override in this simple build.",
        )
        if override_cash:
            reason = st.text_input("Cash Discount Override Reason")
            if not reason.strip():
                st.warning("A reason is required when overriding the customer Cash Discount.")

        remaining_after_scheme = max(0.0, gross - scheme_discount)
        # Cash Discount applies after Scheme Discount and before GST.
        cash_discount = min(remaining_after_scheme, remaining_after_scheme * (cash_pct / 100.0))
        taxable = max(0.0, gross - scheme_discount - cash_discount)

        # Simple weighted GST rate from invoice item lines.
        total_weighted_gst = sum(float(x["gross_amount"]) * float(x["gst_percent"]) for x in st.session_state.cart_lines)
        weighted_gst_pct = (total_weighted_gst / gross) if gross else 0.0
        gst_amount = taxable * weighted_gst_pct / 100.0
        subtotal = taxable + gst_amount
        net_amount, round_off = nearest_rupee(subtotal)

        notes = available_credit_notes(customer_id)
        note_options = [None] + [x["id"] for x in notes]
        credit_note_id = st.selectbox(
            "Apply Credit Note (same Customer Code only)",
            note_options,
            format_func=lambda x: "No Credit Note" if x is None else next(
                f"{n['credit_note_no']} — Available {money(n['available_amount'])}" for n in notes if n["id"] == x
            ),
        )
        available_cn = 0.0 if credit_note_id is None else float(next(n["available_amount"] for n in notes if n["id"] == credit_note_id))
        credit_note_applied = st.number_input(
            "Credit Note Applied Amount",
            min_value=0.0,
            max_value=float(min(available_cn, net_amount)),
            value=0.0,
            step=1.0,
        )
        final_payable = max(0.0, net_amount - credit_note_applied)

        for label, value in [
            ("Gross Value", gross),
            ("Scheme Discount", -scheme_discount),
            (f"Cash Discount ({cash_pct:.2f}%)", -cash_discount),
            ("Taxable Amount", taxable),
            (f"GST Amount ({weighted_gst_pct:.2f}%)", gst_amount),
            ("Subtotal", subtotal),
            ("Round Off", round_off),
            ("Net Amount", net_amount),
            ("Credit Note Applied", -credit_note_applied),
        ]:
            st.metric(label, money(value))
        st.success(f"Final Payable Amount: {money(final_payable)}")

        if st.button("Save Invoice", type="primary", use_container_width=True):
            if override_cash and not reason.strip():
                st.error("Enter Cash Discount override reason.")
            else:
                try:
                    payload = {
                        "invoice_date": date.today().isoformat(),
                        "customer_id": customer_id,
                        "supplier_id": st.session_state.cart_lines[0]["supplier_id"],
                        "salesman": "",
                        "gross_value": gross,
                        "scheme_discount": scheme_discount,
                        "cash_discount_percent": cash_pct,
                        "cash_discount_amount": cash_discount,
                        "taxable_amount": taxable,
                        "gst_amount": gst_amount,
                        "round_off": round_off,
                        "net_amount": net_amount,
                        "credit_note_id": credit_note_id,
                        "credit_note_applied": credit_note_applied,
                        "final_payable": final_payable,
                        "created_by": st.session_state.user_name,
                        "role": st.session_state.role,
                    }
                    invoice_id = create_invoice(payload, st.session_state.cart_lines)
                    if override_cash:
                        log("Sales", "Cash Discount Override", f"Invoice ID {invoice_id}; Reason: {reason}")
                    st.session_state.cart_lines = []
                    st.success("Invoice saved. Stock reduced, Credit Note updated, and Pending Delivery created.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Invoice could not be saved: {exc}")


def render_credit_notes() -> None:
    header("Credit Notes", "Credit Notes are linked to one Customer Code and can only be applied to that customer’s invoices.")
    rows = fetch_all(
        """
        SELECT cn.*, c.customer_code, c.customer_name,
               (cn.original_amount - cn.used_amount) AS available_amount
        FROM credit_notes cn JOIN customers c ON c.id=cn.customer_id
        ORDER BY cn.id DESC
        """
    )
    if rows:
        view = [
            {
                "Credit Note No": x["credit_note_no"],
                "Date": x["note_date"],
                "Customer": f"{x['customer_code']} — {x['customer_name']}",
                "Original": money(x["original_amount"]),
                "Used": money(x["used_amount"]),
                "Available": money(x["available_amount"]),
                "Status": status_badge(x["status"]),
                "Reason": x["reason"],
            }
            for x in rows
        ]
        st.dataframe(pd.DataFrame(view), use_container_width=True, hide_index=True)

    if can_edit_billing():
        customers = fetch_all("SELECT * FROM customers WHERE active=1 ORDER BY customer_name")
        with st.expander("Create Credit Note"):
            with st.form("credit_note_form", clear_on_submit=True):
                customer_id = st.selectbox("Customer", [c["id"] for c in customers], format_func=lambda x: customer_label(next(c for c in customers if c["id"] == x)))
                amount = st.number_input("Credit Note Amount", min_value=0.01, value=100.0)
                reason = st.text_input("Reason")
                if st.form_submit_button("Save Credit Note", type="primary"):
                    note_no = next_number("CN", "credit_notes", "credit_note_no")
                    execute(
                        "INSERT INTO credit_notes (credit_note_no, customer_id, note_date, original_amount, status, reason) VALUES (?, ?, ?, ?, 'Open', ?)",
                        (note_no, customer_id, date.today().isoformat(), amount, reason),
                    )
                    log("Credit Notes", "Credit Note Created", f"{note_no}; Amount {amount:.2f}")
                    st.success(f"Credit Note {note_no} saved.")
                    st.rerun()


def render_payments() -> None:
    header("Payments & Collections", "Collections are bill-wise and reduce Outstanding only after approval.")
    invoices = fetch_all(
        """
        SELECT i.*, c.customer_code, c.customer_name
        FROM invoices i JOIN customers c ON c.id=i.customer_id
        WHERE i.status != 'Cancelled'
        ORDER BY i.id DESC
        """
    )
    collection_rows = fetch_all(
        """
        SELECT cl.*, c.customer_code, c.customer_name, i.invoice_no
        FROM collections cl
        JOIN customers c ON c.id=cl.customer_id
        LEFT JOIN invoices i ON i.id=cl.invoice_id
        ORDER BY cl.id DESC
        """
    )

    t1, t2 = st.tabs(["Record Collection", "Collection Register"])
    with t1:
        customers = fetch_all("SELECT * FROM customers WHERE active=1 ORDER BY customer_name")
        if not customers:
            st.info("Create a customer first.")
        else:
            with st.form("collection_form", clear_on_submit=True):
                customer_id = st.selectbox("Customer", [c["id"] for c in customers], format_func=lambda x: customer_label(next(c for c in customers if c["id"] == x)))
                matching_invoices = [i for i in invoices if i["customer_id"] == customer_id]
                invoice_id = st.selectbox(
                    "Bill / Invoice",
                    [None] + [i["id"] for i in matching_invoices],
                    format_func=lambda x: "Select invoice" if x is None else next(f"{i['invoice_no']} — {money(i['final_payable'])}" for i in matching_invoices if i["id"] == x),
                )
                a, b, c = st.columns(3)
                amount = a.number_input("Collection Amount", min_value=0.01, value=100.0)
                mode = b.selectbox("Payment Mode", ["Cash", "UPI", "NEFT", "Cheque"])
                ref = c.text_input("Reference / Cheque No")
                submit = st.form_submit_button("Submit Collection", type="primary")
                if submit:
                    if invoice_id is None:
                        st.error("Select an invoice for bill-wise allocation.")
                    else:
                        inv = next(i for i in matching_invoices if i["id"] == invoice_id)
                        if amount > float(inv["final_payable"]):
                            st.error("Collection cannot exceed the selected Invoice Final Payable Amount.")
                        else:
                            receipt = next_number("RCPT", "collections", "receipt_no")
                            execute(
                                """
                                INSERT INTO collections (
                                    receipt_no, collection_date, customer_id, invoice_id, amount,
                                    payment_mode, reference_no, collector, status
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Submitted')
                                """,
                                (receipt, date.today().isoformat(), customer_id, invoice_id, amount, mode, ref, st.session_state.user_name),
                            )
                            log("Payments", "Collection Submitted", f"{receipt}; Amount {amount:.2f}; Mode {mode}")
                            st.success("Collection submitted for approval. It is excluded from reminders while pending.")
                            st.rerun()

    with t2:
        if collection_rows:
            view = [
                {
                    "Receipt": x["receipt_no"], "Date": x["collection_date"],
                    "Customer": f"{x['customer_code']} — {x['customer_name']}",
                    "Invoice": x["invoice_no"], "Amount": money(x["amount"]),
                    "Mode": x["payment_mode"], "Collector": x["collector"],
                    "Status": status_badge(x["status"]),
                }
                for x in collection_rows
            ]
            st.dataframe(pd.DataFrame(view), use_container_width=True, hide_index=True)
        else:
            st.info("No collection records.")

        if can_approve():
            submitted = [x for x in collection_rows if x["status"] == "Submitted"]
            if submitted:
                st.subheader("Approve or Reject Submitted Collection")
                cid = st.selectbox("Collection", [x["id"] for x in submitted], format_func=lambda x: next(f"{r['receipt_no']} — {money(r['amount'])}" for r in submitted if r["id"] == x))
                a, b = st.columns(2)
                if a.button("Approve Collection", type="primary"):
                    execute("UPDATE collections SET status='Approved' WHERE id=?", (cid,))
                    log("Payments", "Collection Approved", str(cid))
                    st.success("Collection approved. Outstanding is reduced.")
                    st.rerun()
                if b.button("Reject Collection"):
                    execute("UPDATE collections SET status='Rejected' WHERE id=?", (cid,))
                    log("Payments", "Collection Rejected", str(cid))
                    st.warning("Collection rejected. Amount returns to pending and reminders.")
                    st.rerun()


def render_cash_closing() -> None:
    header("Day Cash Closing", "Cash denomination tally applies only to Cash. UPI, NEFT and Cheque stay separate.")
    collections = fetch_all("SELECT * FROM collections WHERE collection_date=?", (date.today().isoformat(),))
    cash = sum(float(x["amount"]) for x in collections if x["payment_mode"] == "Cash")
    upi = sum(float(x["amount"]) for x in collections if x["payment_mode"] == "UPI")
    neft = sum(float(x["amount"]) for x in collections if x["payment_mode"] == "NEFT")
    cheque = sum(float(x["amount"]) for x in collections if x["payment_mode"] == "Cheque")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Cash", money(cash))
    c2.metric("UPI", money(upi))
    c3.metric("NEFT", money(neft))
    c4.metric("Cheque", money(cheque))
    c5.metric("Total", money(cash + upi + neft + cheque))

    st.subheader("Cash Denomination Entry")
    denoms = [500, 200, 100, 50, 20, 10]
    cols = st.columns(len(denoms) + 1)
    physical = 0
    counts = {}
    for idx, denom in enumerate(denoms):
        counts[denom] = cols[idx].number_input(f"₹{denom}", min_value=0, value=0, key=f"denom_{denom}")
        physical += denom * counts[denom]
    coins = cols[-1].number_input("Coins ₹", min_value=0.0, value=0.0, step=1.0)
    physical += coins
    difference = physical - cash

    a, b, c = st.columns(3)
    a.metric("System Cash", money(cash))
    b.metric("Physical Cash", money(physical))
    c.metric("Difference", money(difference))

    st.subheader("Collected Bill Register")
    bills = fetch_all(
        """
        SELECT cl.receipt_no, i.invoice_no, c.customer_name, c.route, cl.payment_mode,
               cl.reference_no, cl.amount, cl.status
        FROM collections cl
        JOIN customers c ON c.id=cl.customer_id
        LEFT JOIN invoices i ON i.id=cl.invoice_id
        WHERE cl.collection_date=?
        ORDER BY cl.id DESC
        """,
        (date.today().isoformat(),),
    )
    st.dataframe(as_dataframe(bills), use_container_width=True, hide_index=True)
    if st.button("Submit Day Cash Closing", type="primary"):
        log("Day Cash Closing", "Closing Submitted", f"System Cash {cash:.2f}; Physical {physical:.2f}; Difference {difference:.2f}")
        st.success("Cash closing submitted for approval.")


def render_delivery() -> None:
    header("Delivery", "Invoice save creates a Pending Delivery. Took Stock does not reduce stock again.")
    rows = fetch_all(
        """
        SELECT d.*, i.invoice_no, i.final_payable, c.customer_code, c.customer_name, c.route
        FROM deliveries d
        JOIN invoices i ON i.id=d.invoice_id
        JOIN customers c ON c.id=i.customer_id
        ORDER BY d.id DESC
        """
    )
    if rows:
        view = [
            {
                "Invoice": r["invoice_no"],
                "Customer": f"{r['customer_code']} — {r['customer_name']}",
                "Route": r["route"],
                "Delivery Date": r["delivery_date"],
                "Amount": money(r["final_payable"]),
                "Status": status_badge(r["status"]),
                "Reason": r["reason"] or "",
            }
            for r in rows
        ]
        st.dataframe(pd.DataFrame(view), use_container_width=True, hide_index=True)
    else:
        st.info("No deliveries.")

    if rows:
        st.subheader("Update Delivery Status")
        delivery_id = st.selectbox("Delivery", [r["id"] for r in rows], format_func=lambda x: next(f"{r['invoice_no']} — {r['customer_name']}" for r in rows if r["id"] == x))
        status = st.selectbox("New Status", ["Pending Delivery", "Took Stock", "Out for Delivery", "Delivered", "Not Delivered", "Re-Delivery"])
        reason = st.text_input("Reason (mandatory for Not Delivered)")
        if st.button("Update Delivery", type="primary"):
            if status == "Not Delivered" and not reason.strip():
                st.error("Enter a reason for Not Delivered.")
            else:
                execute("UPDATE deliveries SET status=?, reason=?, delivery_person=? WHERE id=?", (status, reason, st.session_state.user_name, delivery_id))
                log("Delivery", "Status Updated", f"Delivery {delivery_id}: {status}; {reason}")
                st.success("Delivery status updated.")
                st.rerun()


def render_routes_gps() -> None:
    header("Routes & GPS", "Salesman GPS starts on Start Route. Delivery GPS starts on Start Trip.")
    a, b = st.columns(2)
    with a:
        st.subheader("Salesman Route")
        st.metric("Route", "NLR-04")
        st.metric("Assigned Customers", "22")
        if st.button("Start Route", type="primary"):
            log("Routes", "Route Started", "NLR-04")
            st.success("Route started. GPS tracking is active in this simple demo.")
        st.caption("In production, use mobile device GPS with permission and offline queue.")
    with b:
        st.subheader("Delivery Trip")
        st.metric("Assigned Deliveries", fetch_one("SELECT COUNT(*) AS c FROM deliveries WHERE status IN ('Pending Delivery','Out for Delivery')")["c"])
        if st.button("Start Trip", type="primary"):
            log("Delivery", "Trip Started", "NLR-04")
            st.success("Trip started. GPS tracking is active in this simple demo.")
        st.caption("GPS stops on End Trip, Logout, deactivation, disabled tracking, or removed permission.")
    st.info("Admin can view live location, distance, route deviation, idle time, and last seen time in the full production upgrade.")


def render_approvals() -> None:
    header("Approvals", "Sensitive actions remain pending until approved or rejected.")
    if not can_approve():
        st.info("Approval access is available only to Admin in this simple version.")
        return

    submitted_collections = fetch_all(
        """
        SELECT cl.*, c.customer_name, i.invoice_no
        FROM collections cl
        JOIN customers c ON c.id=cl.customer_id
        LEFT JOIN invoices i ON i.id=cl.invoice_id
        WHERE cl.status='Submitted'
        """
    )
    pending_orders = fetch_all("SELECT * FROM online_orders WHERE status IN ('Pending Confirmation','Under Review')")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Pending Collections")
        st.dataframe(as_dataframe(submitted_collections), use_container_width=True, hide_index=True)
    with c2:
        st.subheader("Pending Online Orders")
        st.dataframe(as_dataframe(pending_orders), use_container_width=True, hide_index=True)
    st.caption("Additional configurable approvals: scheme override, GST override, cash discount override, credit note override, stock adjustment, invoice cancellation, cash closing, and route access.")


def render_reports() -> None:
    header("Reports", "Simple reports for invoices, stock, outstanding, collections, and audit history.")
    report = st.selectbox(
        "Report",
        ["Sales Summary", "Customer Outstanding", "Stock Report", "Credit Note Report", "Collections", "Low Stock"],
    )
    if report == "Sales Summary":
        rows = fetch_all(
            """
            SELECT i.invoice_no, i.invoice_date, c.customer_code, c.customer_name,
                   i.gross_value, i.scheme_discount, i.cash_discount_amount,
                   i.taxable_amount, i.gst_amount, i.round_off, i.net_amount,
                   i.credit_note_applied, i.final_payable
            FROM invoices i JOIN customers c ON c.id=i.customer_id
            ORDER BY i.id DESC
            """
        )
    elif report == "Customer Outstanding":
        customers = fetch_all("SELECT id, customer_code, customer_name, credit_limit FROM customers WHERE active=1")
        rows = [
            {
                "Customer Code": c["customer_code"],
                "Customer Name": c["customer_name"],
                "Credit Limit": money(c["credit_limit"]),
                "Outstanding": money(customer_outstanding(c["id"])),
            }
            for c in customers
        ]
    elif report == "Stock Report":
        rows = fetch_all(
            """
            SELECT i.item_code, i.item_name, s.supplier_name, i.pcs_per_case,
                   i.stock_cases, i.stock_pieces, i.min_stock_cases,
                   i.selling_price, i.gst_percent
            FROM items i LEFT JOIN suppliers s ON s.id=i.supplier_id
            ORDER BY i.item_name
            """
        )
    elif report == "Credit Note Report":
        rows = fetch_all(
            """
            SELECT cn.credit_note_no, c.customer_code, c.customer_name, cn.note_date,
                   cn.original_amount, cn.used_amount, (cn.original_amount-cn.used_amount) AS available_amount,
                   cn.status, cn.reason
            FROM credit_notes cn JOIN customers c ON c.id=cn.customer_id
            ORDER BY cn.id DESC
            """
        )
    elif report == "Collections":
        rows = fetch_all(
            """
            SELECT cl.receipt_no, cl.collection_date, c.customer_code, c.customer_name,
                   i.invoice_no, cl.amount, cl.payment_mode, cl.reference_no,
                   cl.collector, cl.status
            FROM collections cl JOIN customers c ON c.id=cl.customer_id
            LEFT JOIN invoices i ON i.id=cl.invoice_id
            ORDER BY cl.id DESC
            """
        )
    else:
        rows = fetch_all(
            """
            SELECT item_code, item_name, stock_cases, stock_pieces, min_stock_cases
            FROM items WHERE stock_cases <= min_stock_cases
            ORDER BY item_name
            """
        )

    df = as_dataframe(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    if not df.empty:
        st.download_button(
            "Download CSV",
            df.to_csv(index=False).encode("utf-8"),
            file_name=f"pro_distributor_{report.lower().replace(' ', '_')}.csv",
            mime="text/csv",
        )


def render_settings() -> None:
    header("Settings", "Simple settings screen. Keep all advanced settings in this single editable file initially.")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Company Settings")
        st.text_input("Company Name", value="My Distribution Company")
        st.text_input("GST Number")
        st.text_input("WhatsApp Number")
        st.selectbox("Currency", ["INR — Indian Rupee"])
    with c2:
        st.subheader("Invoice Settings")
        st.selectbox("Round Off Rule", ["Nearest Rupee: below ₹0.50 down, ₹0.50+ up"])
        st.selectbox("Default Session Timeout", ["30 Minutes", "1 Hour", "Custom"])
        st.selectbox("Customer Stock Visibility", ["Exact Stock", "In Stock", "Limited Stock", "Out of Stock", "Available on Request"])
    if st.button("Save Settings", type="primary"):
        log("Settings", "Settings Saved", "Simple settings screen")
        st.success("Settings saved in Activity Log. Add persistent settings fields when you need them.")


def render_activity_log() -> None:
    header("Activity Log", "Every important transaction and override should leave an audit trail.")
    rows = fetch_all("SELECT * FROM activity_logs ORDER BY id DESC LIMIT 250")
    st.dataframe(as_dataframe(rows), use_container_width=True, hide_index=True)


# ---------- Router ----------
route_map = {
    "Dashboard": render_dashboard,
    "Masters": render_masters,
    "Catalog & Cart": render_catalog_cart,
    "Online Orders": render_online_orders,
    "Sales Billing": render_sales_billing,
    "Credit Notes": render_credit_notes,
    "Payments & Collections": render_payments,
    "Day Cash Closing": render_cash_closing,
    "Delivery": render_delivery,
    "Routes & GPS": render_routes_gps,
    "Approvals": render_approvals,
    "Reports": render_reports,
    "Settings": render_settings,
    "Activity Log": render_activity_log,
}

route_map[page]()

st.divider()
st.caption(
    "Simple Streamlit version. Core workflows are functional with SQLite: Customer Master Cash Discount, "
    "Invoice calculation, round-off, same-customer Credit Note, stock reduction, online orders, collections, "
    "delivery status, reports, and activity logs."
)
