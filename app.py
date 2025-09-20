import streamlit as st
import pandas as pd
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.units import mm
from datetime import datetime

# --------------------
# Simple Streamlit app: "HYD Builder Quote Generator"
# Features:
# - Login (admin/admin)
# - Customer-facing Quote Builder
# - Generates downloadable PDF (3-4 pages) and Excel
# - Saves quote in-session (My Quotes)
# - Typical Indian construction rates (sample) — tweak as needed
# --------------------

st.set_page_config(page_title="HYD Builder — Quote Generator", layout="wide")

# ---------- Sample rates (typical Indian style) ----------
# These are example unit costs. Change as per your local costing in Hyderabad.
SAMPLE_RATES = {
    "Cement (bag, 50kg)": 420,            # ₹ per bag
    "Bricks (1000 nos)": 7000,            # ₹ per 1000
    "Sand (per cu.m)": 1500,              # ₹ per cu.m
    "Steel (per ton)": 65000,             # ₹ per ton
    "Plastering (labor per sq.ft)": 25,   # ₹ per sq.ft
    "Flooring (tiles per sq.ft incl material+labour)": 250, # ₹ per sq.ft
    "Painting (per sq.ft)": 18,           # ₹ per sq.ft
    "Electrical (per point incl material+labour)": 1200,    # ₹ per point
}

GST_PERCENT = 18

# ---------- Authentication ----------
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if 'username' not in st.session_state:
    st.session_state.username = ''


def login_widget():
    st.sidebar.title("Login")
    if st.session_state.logged_in:
        st.sidebar.success(f"Logged in as {st.session_state.username}")
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = ''
            st.experimental_rerun()
    else:
        username = st.sidebar.text_input("Username")
        password = st.sidebar.text_input("Password", type="password")
        if st.sidebar.button("Login"):
            if username == 'admin' and password == 'admin':
                st.session_state.logged_in = True
                st.session_state.username = username
                st.sidebar.success("Login successful")
                st.experimental_rerun()
            else:
                st.sidebar.error("Invalid credentials")

login_widget()

# ---------- Navigation ----------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Home", "Quote Builder", "My Quotes", "Admin"])

# ---------- Utilities ----------

def calc_item_total(item_name, qty, unit_type='unit'):
    rate = SAMPLE_RATES.get(item_name, 0)
    return rate * qty


def calculate_quote(selected_items, extras, discount_percent=0):
    rows = []
    subtotal = 0
    for it in selected_items:
        name = it['name']
        qty = it['qty']
        unit = it.get('unit', 'unit')
        rate = SAMPLE_RATES.get(name, 0)
        total = rate * qty
        rows.append({
            'Item': name,
            'Qty': qty,
            'Unit Price (₹)': rate,
            'Total (₹)': total
        })
        subtotal += total

    # extras: dict of extra charges (like design fee)
    extras_total = sum(extras.values()) if extras else 0
    subtotal += extras_total
    discount_amt = subtotal * (discount_percent / 100)
    taxable = subtotal - discount_amt
    gst_amt = taxable * GST_PERCENT / 100
    grand_total = taxable + gst_amt

    return {
        'rows': rows,
        'extras': extras,
        'subtotal': subtotal,
        'discount_amt': discount_amt,
        'taxable': taxable,
        'gst_amt': gst_amt,
        'grand_total': grand_total
    }


def generate_pdf_bytes(company_info, customer_info, quote_calc, quote_meta):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    styleH = styles['Heading1']
    styleN = styles['Normal']
    style_small = ParagraphStyle('small', parent=styleN, fontSize=9)

    story = []

    # Page 1: Cover + basic details
    story.append(Paragraph(company_info['name'], ParagraphStyle('title', fontSize=18, leading=22)))
    story.append(Paragraph(company_info['address'], style_small))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Quote for: {customer_info['name']}", styles['Heading2']))
    story.append(Paragraph(f"Phone: {customer_info['phone']} | Email: {customer_info.get('email','-')}", style_small))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Quote ID: {quote_meta['id']}", style_small))
    story.append(Paragraph(f"Date: {quote_meta['date']}", style_small))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Project Summary:", styles['Heading3']))
    story.append(Paragraph(quote_meta.get('project_summary','-'), styleN))
    story.append(PageBreak())

    # Page 2: Itemized costs
    story.append(Paragraph("Detailed Cost Breakup", styles['Heading2']))
    story.append(Spacer(1, 6))

    data = [["Item", "Qty", "Unit Price (₹)", "Total (₹)"]]
    for r in quote_calc['rows']:
        data.append([r['Item'], r['Qty'], f"{r['Unit Price (₹)']:,}", f"{r['Total (₹)']:,}"])

    # extras
    if quote_calc['extras']:
        for k, v in quote_calc['extras'].items():
            data.append([k, '-', '-', f"{v:,}"])

    tbl = Table(data, colWidths=[140*mm/3, 40*mm/3, 50*mm/3, 50*mm/3])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('ALIGN', (1,1), (-1,-1), 'RIGHT')
    ]))
    story.append(tbl)
    story.append(Spacer(1, 12))

    # totals
    story.append(Paragraph(f"Subtotal: ₹ {quote_calc['subtotal']:,}", styleN))
    story.append(Paragraph(f"Discount: ₹ {quote_calc['discount_amt']:,}", styleN))
    story.append(Paragraph(f"Taxable Amount: ₹ {quote_calc['taxable']:,}", styleN))
    story.append(Paragraph(f"GST ({GST_PERCENT}%): ₹ {quote_calc['gst_amt']:,}", styleN))
    story.append(Paragraph(f"Grand Total: ₹ {quote_calc['grand_total']:,}", styles['Heading3']))
    story.append(PageBreak())

    # Page 3: Notes, terms, approximate timelines
    story.append(Paragraph("Terms & Conditions", styles['Heading2']))
    notes = [
        "This is an indicative quotation based on current market rates and scope provided.",
        "Validity: 30 days from the date of quotation.",
        "GST and other statutory charges are extra and included above.",
        "Work will be executed as per mutually agreed contract and schedule.",
        "Advance payment: 20% at signing, milestones as per contract."
    ]
    for n in notes:
        story.append(Paragraph(f"• {n}", styleN))
        story.append(Spacer(1,4))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Estimate Timeline:", styles['Heading3']))
    story.append(Paragraph(quote_meta.get('timeline','To be decided'), styleN))
    story.append(Spacer(1, 12))

    # Page 4: Signature / approval
    story.append(PageBreak())
    story.append(Paragraph("Approval", styles['Heading2']))
    story.append(Spacer(1,12))
    story.append(Paragraph("Customer Signature: ____________________", styleN))
    story.append(Spacer(1,36))
    story.append(Paragraph(company_info['name'] + "\nAuthorized Signatory", styleN))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_excel_bytes(company_info, customer_info, quote_calc, quote_meta):
    output = io.BytesIO()
    # Create DataFrame
    df = pd.DataFrame(quote_calc['rows'])
    extras = pd.Series(quote_calc['extras']) if quote_calc['extras'] else pd.Series()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Items', index=False)
        # Summary sheet
        summary = pd.DataFrame({
            'Description': ['Subtotal', 'Discount', 'Taxable', f'GST ({GST_PERCENT}%)', 'Grand Total'],
            'Amount (₹)': [quote_calc['subtotal'], quote_calc['discount_amt'], quote_calc['taxable'], quote_calc['gst_amt'], quote_calc['grand_total']]
        })
        summary.to_excel(writer, sheet_name='Summary', index=False)
        # Company & customer info
        info = pd.DataFrame({
            'Company': [company_info['name']],
            'Company Address': [company_info['address']],
            'Customer': [customer_info['name']],
            'Customer Phone': [customer_info['phone']],
            'Quote ID': [quote_meta['id']],
            'Date': [quote_meta['date']]
        })
        info.to_excel(writer, sheet_name='Info', index=False)

    output.seek(0)
    return output.getvalue()

# ---------- Pages ----------
company_info = {
    'name': 'Hyderabad Builders & Developers',
    'address': 'Banjara Hills, Hyderabad, Telangana — 500034\nPhone: +91-40-XXXX-XXXX'
}

if page == "Home":
    st.title("Welcome to HYD Builder — Quick Quote")
    st.markdown("""
    ### Quick and transparent construction quotes for Hyderabad (HYD)
    - Select items, enter quantities — get an instant estimate.
    - Download full, printable PDF (4 pages) or Excel.
    - Admin login available (username: `admin`, password: `admin`).
    """)
    st.image('https://images.unsplash.com/photo-1529429617124-9f6a6d0a7f54?auto=format&fit=crop&w=1350&q=80', use_column_width=True)


elif page == "Quote Builder":
    st.title("Build a Quote — HYD Builder")

    with st.form(key='quote_form'):
        st.subheader("Customer Details")
        cname = st.text_input("Customer Name", placeholder='e.g., Mr. Ramesh')
        cphone = st.text_input("Phone Number")
        cemail = st.text_input("Email (optional)")

        st.subheader("Project")
        project_summary = st.text_area("Project Summary / Address", height=80, placeholder='e.g., 1200 sq.ft house renovation at Kukatpally')
        timeline = st.text_input("Approx. Timeline", value='3 months')

        st.subheader("Select Items & Quantities")
        selected_items = []
        for name, rate in SAMPLE_RATES.items():
            col1, col2 = st.columns([3,1])
            with col1:
                include = st.checkbox(f"Include {name} (₹ {rate:,})", key=f"inc_{name}")
            with col2:
                qty = st.number_input(f"Qty ({name})", min_value=0.0, step=1.0, key=f"qty_{name}")
            if include and qty > 0:
                selected_items.append({'name': name, 'qty': qty})

        st.subheader("Extras & Discounts")
        design_fee = st.number_input("Design / Consultancy Fee (₹)", min_value=0.0, value=0.0)
        misc = st.number_input("Other Misc Charges (₹)", min_value=0.0, value=0.0)
        discount = st.number_input("Discount (%)", min_value=0.0, max_value=100.0, value=0.0)

        submit = st.form_submit_button("Generate Quote")

    if submit:
        if not cname or not cphone:
            st.error("Please enter customer name and phone number.")
        elif len(selected_items) == 0:
            st.error("Please include at least one item in the quote.")
        else:
            extras = {}
            if design_fee > 0: extras['Design Fee'] = design_fee
            if misc > 0: extras['Misc Charges'] = misc

            quote_meta = {
                'id': f"HYD-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'date': datetime.now().strftime('%d-%b-%Y'),
                'project_summary': project_summary,
                'timeline': timeline
            }

            quote_calc = calculate_quote(selected_items, extras, discount_percent=discount)

            st.success("Quote generated — see summary below")
            st.subheader("Summary")
            df = pd.DataFrame(quote_calc['rows'])
            st.dataframe(df)

            st.markdown(f"**Subtotal:** ₹ {quote_calc['subtotal']:,}")
            st.markdown(f"**Discount:** ₹ {quote_calc['discount_amt']:,}")
            st.markdown(f"**GST ({GST_PERCENT}%):** ₹ {quote_calc['gst_amt']:,}")
            st.markdown(f"### Grand Total: ₹ {quote_calc['grand_total']:,}")

            customer_info = {'name': cname, 'phone': cphone, 'email': cemail}

            # Generate PDF & Excel bytes
            pdf_bytes = generate_pdf_bytes(company_info, customer_info, quote_calc, quote_meta)
            excel_bytes = generate_excel_bytes(company_info, customer_info, quote_calc, quote_meta)

            st.download_button("Download Quote as PDF (4 pages)", data=pdf_bytes, file_name=f"quote_{quote_meta['id']}.pdf", mime='application/pdf')
            st.download_button("Download Quote as Excel", data=excel_bytes, file_name=f"quote_{quote_meta['id']}.xlsx", mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

            # Save to session (My Quotes)
            if 'my_quotes' not in st.session_state:
                st.session_state.my_quotes = []
            st.session_state.my_quotes.append({
                'meta': quote_meta,
                'customer': customer_info,
                'calc': quote_calc
            })


elif page == "My Quotes":
    st.title("My Quotes")
    if 'my_quotes' not in st.session_state or len(st.session_state.my_quotes) == 0:
        st.info("No quotes generated in this session. Create one from 'Quote Builder'.")
    else:
        for q in reversed(st.session_state.my_quotes):
            box = st.expander(f"{q['meta']['id']} — {q['customer']['name']} — ₹ {q['calc']['grand_total']:,}")
            with box:
                st.write(q['meta'])
                st.write(q['customer'])
                st.dataframe(pd.DataFrame(q['calc']['rows']))
                pdf_bytes = generate_pdf_bytes(company_info, q['customer'], q['calc'], q['meta'])
                excel_bytes = generate_excel_bytes(company_info, q['customer'], q['calc'], q['meta'])
                st.download_button("Download PDF", data=pdf_bytes, file_name=f"{q['meta']['id']}.pdf", mime='application/pdf')
                st.download_button("Download Excel", data=excel_bytes, file_name=f"{q['meta']['id']}.xlsx", mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


elif page == "Admin":
    st.title("Admin Panel")
    if not st.session_state.logged_in:
        st.warning("Login as admin to access admin features.")
    else:
        st.success("Welcome, admin")
        st.subheader("Manage Rates (in ₹)")
        for name in list(SAMPLE_RATES.keys()):
            new_rate = st.number_input(f"Rate — {name}", min_value=0.0, value=float(SAMPLE_RATES[name]), key=f"rate_{name}")
            SAMPLE_RATES[name] = new_rate

        st.markdown("---")
        st.subheader("Company Info")
        company_info['name'] = st.text_input("Company Name", value=company_info['name'])
        company_info['address'] = st.text_area("Company Address", value=company_info['address'])

        st.markdown("---")
        st.write("Note: This demo stores quotes only in browser session. For persistence, connect to a database (e.g., Snowflake, Postgres).")

# Footer
st.markdown("---")
st.caption("HYD Builder — Quote Generator · Demo · Made for Hyderabad builders")
