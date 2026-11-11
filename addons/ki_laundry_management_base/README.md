# 🧺 Laundry Management - Base

Technical name: `ki_laundry_management_base` · Odoo 19.0 · Community and Enterprise · by **Kalvyai**

Complete core solution for laundromats, dry cleaners, pressing and wash-and-fold operations in Odoo: counter intake, barcode garment tags, workstation floor tracking, per-piece and per-kg weight pricing, customer notifications, and invoicing.

---

## ✨ Features

- 🏷️ **Garments as Variants & Services as Products**: Manage services (Wash, Dry Clean, Iron, Wash & Fold) and garments (Shirt, Saree, Blanket) using native product variants and pricelists.
- 💰 **Flexible Pricing Grid**: Simple matrix screen to switch services on/off for garments and set per-piece, per-set, or per-kg prices.
- ⚖️ **Weighing & Minimum Charge**: Support for weighed loads (laundry bags) with minimum billed quantities and intake weighing wizards.
- 🔖 **Single Barcode Tag Per Garment**: Generate one unique barcode tag per piece/bag even across multiple process steps.
- 🏭 **Workstation Dashboard & Tag Scanning**: Floor operators select their station (Wash, Iron, Pack...) and scan tags or click *Done* to advance garments.
- 📅 **Automated Turnaround & Due Dates**: Calculate order completion dates from service durations, working calendar schedules, and holidays.
- ⚡ **Urgent Orders & Add-ons**: Apply urgent surcharges and add-on services (starch, fragrance, stain removal) seamlessly.
- 🏷️ **Offers & Frozen Pricing**: Support promotional offers (e.g., 10% off blankets); prices are frozen at intake date (`price_date`) so later weighing retains original offer rates.
- 🧾 **Invoicing & Deposit Advances**: Create customer invoices, record advances, issue credit notes, and prevent accidental double-invoicing.
- 📦 **Partial Delivery & Stop/Return**: Support partial handovers, order cancellation with optional cancellation fees, and rework logging for damaged items.
- ⏰ **Unclaimed Garment Reminders & Storage Fees**: Automated cron notifications for uncollected orders and configurable storage fees after grace periods.
- 📧 **Automated Email Notifications**: Customer emails on order reception, completion (ready to collect), delivery, and unclaimed reminders.
- 🖨️ **Receipts & Thermal Tags**: 80 mm POS-style receipts, printable garment tags with barcodes, and standard A4 order summaries.

---

## 📦 Installation

1. 📁 Copy `ki_laundry_management_base` into your Odoo addons path.
2. 🔄 Restart Odoo and update the apps list via **Apps ▸ Update Apps List**.
3. ⬇️ Search for **Laundry Management - Base** and click **Install**.
4. ⬆️ After updating module files, upgrade using Odoo CLI: `-u ki_laundry_management_base` or via the Apps list.

---

## 🛠️ Module flow

### 1️⃣ Configure Services & Process Steps

- ⚙️ Go to **Laundry ▸ Configuration ▸ Process Steps**: define stations (e.g., Tagging, Wash, Dry, Iron, Pack) and their sequence.
- 🧼 Go to **Laundry ▸ Configuration ▸ Services**: configure laundry services, assign process steps, pricing mode (*Per Piece* or *Per Kg*), and turnaround hours.
- 👚 Go to **Laundry ▸ Configuration ▸ Garments**: define garment types and categories.

### 2️⃣ Set Prices & System Settings

- 💵 Go to **Laundry ▸ Configuration ▸ Prices**: use the visual price grid to enable services for garments and set rates.
- ⚙️ Go to **Laundry ▸ Configuration ▸ Settings**:
  - Set working hours calendar for turnaround estimation.
  - Choose payment policy (Prepaid, Postpaid, Advance).
  - Configure notification emails, unclaimed reminder days, and storage fee policies.

### 3️⃣ Counter Order Intake

- 📝 Go to **Laundry ▸ Orders ▸ All Orders ▸ New**.
- 👤 Select customer, pricelist, and priority (Normal / Urgent).
- 🧺 Add intake lines (Garment, Service, Quantity or Kg).
- 🔘 Click **Receive Garments**: generates item tags, schedules due dates, and locks pricing.
- 🖨️ Print receipt and garment tags.

### 4️⃣ Workstation Tracking

- 🏭 Operators open **Laundry ▸ Operations ▸ Workstation**.
- 📍 Select active station (e.g., Washing or Ironing).
- 📷 Scan garment barcode (or order receipt barcode to complete all items in the order), or click **Done** on garment cards.
- 🚚 Once all garments pass their final step, order status automatically advances to **Ready**.

### 5️⃣ Delivery & Invoicing

- 📦 When the customer arrives, click **Deliver**: scan tags or deliver all.
- 💳 Click **Create Invoice** to generate standard account invoice or register advance payments.

---

## 🧩 Compatibility

- ✅ **Odoo Community Edition**
- ✅ **Odoo Enterprise Edition**
- ✅ **Base dependencies**: `mail`, `product`, `account`, `barcodes`, `resource`
- ✅ **Extensions**: Ready foundation for POS and Website laundry extensions (`ki_laundry_pos`, `ki_laundry_website`).

---

## ⚠️ Known limitations

- Custom backend modules are not supported on Odoo Online (SaaS); requires Odoo.sh or an On-Premise installation.
- Thermal tag printing requires an ESC/POS printer or standard browser PDF printing.
- Automated email alerts require configured outgoing mail servers in Odoo.

---

## 🗂️ Technical overview

| Path | Purpose |
|---|---|
| `models/laundry_order.py` | Core order workflow, state transitions, delivery logic, and recalculation |
| `models/laundry_order_intake.py` | Intake lines entered by counter cashiers |
| `models/laundry_order_item.py` | Physical garment tracking, barcodes, station routes, and rework status |
| `models/laundry_process_step.py` | Configurable workstations/process steps |
| `models/product_template.py` | Service and garment attribute configuration |
| `wizard/` | Dedicated wizards for intake split, weighing, cancellation, delivery, rework, and invoicing |
| `static/src/workstation/` | Interactive workstation OWL client action for shop-floor tag scanning |
| `static/src/price_grid/` | Visual price matrix editor OWL component |
| `static/src/dashboard/` | Real-time laundry management dashboard with station loads and KPIs |
| `report/` | QWeb templates for 80mm thermal receipts, garment barcode tags, and A4 orders |

---

## 💁 Support

- 🌐 Website: https://kalvyai.com
- 📧 Support: support@kalvyai.com

## 📜 License

Copyright (c) 2026-Present Kalvyai. All Rights Reserved.  
Licensed under the kalvyai Software Licence Agreement (Other proprietary): one licence per production database, no redistribution. See the `LICENSE` file.
