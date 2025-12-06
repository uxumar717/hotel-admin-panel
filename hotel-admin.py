import streamlit as st
import json
from datetime import date, timedelta, datetime
import matplotlib.pyplot as plt
import pandas as pd
import io
import os
import base64


# --- FILE PATHS ---
ROOMS_FILE = 'rooms.json'
EARNINGS_FILE = 'earnings.json'

# --- JSON UTILITY FUNCTIONS ---

def load_json(filename):
    """Loads data from a JSON file. Initializes with default structure if missing."""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        if filename == ROOMS_FILE:
            return {} 
        elif filename == EARNINGS_FILE:
            return {"balance": 0.0, "history": []}
        return {}
    except json.JSONDecodeError:
        st.error(f"Error decoding JSON from {filename}. File might be corrupted.")
        return {} if filename == ROOMS_FILE else {"balance": 0.0, "history": []}

def save_json(filename, data):
    """Saves data back to a JSON file."""
    try:
        with open(filename, 'w', encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        st.error(f"Error writing to file {filename}: {e}")

# Load room data globally (Streamlit runs script from top on every interaction)
rooms = load_json(ROOMS_FILE)
rooms_by_id = {details["id"]: name for name, details in rooms.items()}
month = date.today().month

# --- NEW FINANCIAL LOGIC ---

def log_transaction(amount, description, room_id):
    """
    Updates the global balance and records history in earnings.json.
    amount: Positive for Income, Negative for Refunds/Expenses.
    """
    earnings = load_json(EARNINGS_FILE)
    
    amount = float(amount)
    earnings['balance'] += amount
    
    # Create Record
    record = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "description": description,
        "amount": round(amount, 2), # Round for currency
        "room_id": room_id,
        "running_balance": round(earnings['balance'], 2)
    }
    
    earnings['history'].append(record)
    save_json(EARNINGS_FILE, earnings)
    st.toast(f"Transaction Logged: {description} | Amount: Rs. {abs(amount):,.2f}", icon="💸")

# --- ROOM MANAGEMENT FUNCTIONS ---

def show_available_rooms():
    st.header("🛏️ Available Rooms")

    # Extract floors from room names
    floors = sorted({
        int(name.split("Floor")[1].strip())
        for name in rooms.keys()
        if "Floor" in name
    })
    floors.insert(0, "All Floors")

    # Floor selection
    selected_floor = st.selectbox("Filter by Floor", floors)

    # Show rooms
    st.subheader("🏨 Room List")
    any_room = False

    for name, d in rooms.items():
        # Extract room's floor
        if "Floor" in name:
            room_floor = int(name.split("Floor")[1].strip())
        else:
            continue

        # Match selected floor
        if selected_floor != "All Floors" and room_floor != selected_floor:
            continue

        any_room = True
        availability = "🟢 Available" if d.get("available") else "🔴 Booked"

        st.info(
            f"Floor {room_floor} | 🆔 {d['id']} | {name} — {d['type']} "
            f"| 💰 {d['price']} | {availability}"
        )

    if not any_room:
        st.warning("No rooms found on this floor.")


def book_room():
    st.header("📘 Book a Room")

    # NEW: Display success message if a booking was just completed
    if 'booking_success_message' in st.session_state:
        st.success(st.session_state.booking_success_message)
        del st.session_state.booking_success_message
        st.session_state.pop("booking_data", None)
        st.rerun() # Rerun to fully clear all inputs after showing success

    name = st.text_input("Customer Name", key="book_name")
    cnic = st.text_input("CNIC", key="book_cnic")

    start_date = date.today()
    date_range = st.date_input(
        "Select Check-in and Check-out Dates",
        value=(start_date, start_date + timedelta(days=1)),
        min_value=start_date,
        key="date_range"
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        check_in, check_out = date_range
        days = (check_out - check_in).days
        st.write(f"Number of days: {days}")
        if days < 1:
            st.error("Check-out date must be after check-in.")
            return
    else:
        st.warning("Please select both check-in and check-out dates.")
        return

    # UPDATED — MULTISELECT WITH TYPE + PRICE
    options = []
    label_to_room = {}

    for rname, rdata in rooms.items():
        if rdata["available"]:
            room_type = rdata.get("type")
            price = rdata.get("price")
            label = f"{rname} — {room_type} — Rs {price:,.2f}"
            options.append(label)
            label_to_room[label] = rname

    selected_labels = st.multiselect("Select Rooms to Book", options, key="selected_labels")
    selected_rooms = [label_to_room[l] for l in selected_labels]

    # STEP 1 — CALCULATE PRICE
    if st.button("Calculate Price"):
        if not name or not cnic:
            st.error("Please enter name & CNIC.")
            return
        if not selected_rooms:
            st.error("Please select at least one room.")
            return

        # Initialize booking_data
        st.session_state.booking_data = []

        for rname in selected_rooms:
            room = rooms[rname]
            daily_price = float(room["price"])

            # Apply 15% discount for July-Dec (7-12)
            if 7 <= month <= 12:
                daily_price = round(daily_price * 0.85, 2)

            total_price = round(daily_price * days, 2)
            pay_key = f"pay_amount_{rname}"

            st.session_state.booking_data.append({
                "room": rname,
                "daily_price": daily_price,
                "total_price": total_price,
                "pay_key": pay_key
            })
        # Note: No st.rerun() needed here, Streamlit will redraw with new state.

    # PAYMENT INPUTS
    if "booking_data" in st.session_state and st.session_state.booking_data:
        st.subheader("💵 Payment Details")

        for entry in st.session_state.booking_data:
            rname = entry["room"]
            total_price = entry["total_price"]
            pay_key = entry["pay_key"]

            # Use value= to ensure state is maintained across runs
            st.number_input(
                f"{rname} — Total: {total_price:,.2f} | Amount paid now:",
                min_value=0.0,
                max_value=float(total_price),
                value=st.session_state.get(pay_key, 0.0),
                key=pay_key
            )

        # CONFIRM BUTTON
        if st.button("Confirm All Bookings and Process Payment"):
            if not name or not cnic:
                st.error("Customer details are missing. Please re-enter.")
                return

            booked_any = False
            total_paid_now = 0.0
            
            for entry in st.session_state.booking_data:
                rname = entry["room"]
                total_price = entry["total_price"]
                daily_price = entry["daily_price"]
                pay_key = entry["pay_key"]

                # Get final payment from session state
                pay_now = float(st.session_state.get(pay_key, 0.0))
                remaining = round(total_price - pay_now, 2)

                room = rooms[rname]
                room["available"] = False
                room["Booked-To"] = {
                    "Name": name,
                    "CNIC": cnic,
                    "Check-in": check_in.isoformat(),
                    "Check-Out": check_out.isoformat(),
                    "Outstanding": remaining,
                    "Paid": pay_now,
                    "Total Price": total_price,
                    "Daily Rate": daily_price,
                    "Days": days,
                }
                
                # Log transaction for the initial payment/deposit
                if pay_now > 0:
                    log_transaction(pay_now, f"INCOME: Initial Deposit for {rname}", room['id'])
                    total_paid_now += pay_now

                booked_any = True

            if booked_any:
                save_json(ROOMS_FILE, rooms)
                
                # FIX: Set a success message in session state to survive the next run
                st.session_state.booking_success_message = (
                    f"Successfully booked {len(st.session_state.booking_data)} room(s) for {name}. "
                    f"Total Paid: PKR {total_paid_now:,.2f}"
                )
                
                # Clear all user inputs keys to ensure a clean slate
                st.session_state.pop("book_name", None)
                st.session_state.pop("book_cnic", None)
                st.session_state.pop("date_range", None)
                st.session_state.pop("selected_labels", None)
                st.session_state.pop("booking_data", None) # Important to hide payment section
                
                # Force a rerun to show the success message at the top and reset the form
                st.rerun()
            else:
                st.info("No rooms were booked.")

def check_out():
    st.header("🚪 Standard Check Out")

    # Gather all current bookings
    bookings = []
    for rname, room in rooms.items():
        booked = room.get("Booked-To")
        if booked and not room["available"]:
            bookings.append({
                "Room": rname,
                "Name": booked["Name"],
                "CNIC": booked["CNIC"],
                "Check-in": booked["Check-in"],
                "Check-out": booked["Check-Out"],
                "Outstanding": float(booked.get("Outstanding", 0) or 0),
                "Paid": float(booked.get("Paid", 0) or 0),
                "Room ID": room["id"]
            })

    if not bookings:
        st.info("No rooms are currently booked.")
        return

    # Display all bookings
    df = pd.DataFrame(bookings)
    df_display = df[['Room', 'Name', 'Check-out', 'Outstanding']].copy()
    df_display['Outstanding'] = df_display['Outstanding'].apply(lambda x: f"PKR {x:,.2f}")
    st.subheader("Current Bookings")
    st.dataframe(df_display, hide_index=True)

    # Select booking to check out
    options = [f"{b['Name']} ({b['CNIC']}) - {b['Room']}" for b in bookings]
    selected_option = st.selectbox("Select booking to check out", options)

    if selected_option:
        # Find the selected booking object
        selected_booking = next(b for b in bookings if f"{b['Name']} ({b['CNIC']}) - {b['Room']}" == selected_option)
        room_name = selected_booking["Room"]
        room_details = rooms[room_name]
        
        # Standard checkout only allows check out if dues are cleared
        outstanding = selected_booking["Outstanding"]

        if st.button(f"Standard Check Out {room_name}"):
            if outstanding <= 0:
                # Room check out (available=True)
                room_details["available"] = True
                room_details["Booked-To"] = None
                
                save_json(ROOMS_FILE, rooms)
                st.success(f"{selected_booking['Name']} checked out from {room_name}.")
                st.rerun()
            else:
                st.warning(f"Please clear outstanding dues first: PKR {outstanding:.2f}")


def pay_amnt():
    st.header("💳 Pay Outstanding Dues")
    cnic = st.text_input("Enter CNIC", key="pay_cnic_input")
    
    if st.button("Fetch Dues", key="fetch_dues_btn"):
        if not cnic:
            st.warning("Please enter a CNIC first.")
            return
        
        customer_rooms = [
            (name, d) for name, d in rooms.items()
            if d.get("Booked-To") and d["Booked-To"].get("CNIC") == cnic
        ]

        if not customer_rooms:
            st.error("No booking found for this CNIC.")
            st.session_state.pop("dues_data", None)
            return

        st.session_state["dues_data"] = [
            {
                "room": name,
                "id": d["id"],
                "due": float(d["Booked-To"].get("Outstanding", 0)),
                "paid": float(d["Booked-To"].get("Paid", 0)),
                "pay_key": f"pay_input_{name}"
            }
            for name, d in customer_rooms
            if float(d["Booked-To"].get("Outstanding", 0)) > 0
        ]
        st.rerun() # Rerun to display payment UI

    if "dues_data" in st.session_state and st.session_state["dues_data"]:
        st.subheader("Outstanding Rooms:")

        for entry in st.session_state["dues_data"]:
            room_name = entry["room"]
            room_id = entry["id"]
            due = entry["due"]
            pay_key = entry["pay_key"]

            st.write(f"🏠 {room_name} — Outstanding: {due:,.2f}")

            # Payment input (must exist on rerun)
            amnt = st.number_input(
                f"Enter amount to pay for {room_name}",
                min_value=0.0,
                max_value=float(due),
                key=pay_key,
                value=0.0
            )

            if st.button(f"Confirm Payment for {room_name}", key=f"btn_{room_name}"):
                if amnt <= 0:
                    st.warning("Amount must be greater than zero.")
                    continue
                
                # UPDATE VALUES 
                new_outstanding = round(due - amnt, 2)
                new_paid = round(rooms[room_name]["Booked-To"]["Paid"] + amnt, 2)
                
                rooms[room_name]["Booked-To"]["Outstanding"] = new_outstanding
                rooms[room_name]["Booked-To"]["Paid"] = new_paid
                
                # Log the income
                log_transaction(amnt, f"INCOME: Dues Payment for {room_name}", room_id)
                
                save_json(ROOMS_FILE, rooms)
                
                st.success(
                    f"Payment recorded! Remaining Outstanding: {new_outstanding:,.2f}"
                )
                if new_outstanding <= 0:
                    st.info(f"✅ {room_name} is now fully paid!")
                    
                st.rerun() # Rerun to update the list


def see_outstanding():
    st.header("📋 Outstanding Customers")
    found = False
    data = []
    for name, d in rooms.items():
        booked = d.get("Booked-To")
        if booked:
            outstanding = float(booked.get("Outstanding", 0) or 0)
            if outstanding > 0:
                data.append({
                    "Room": name,
                    "Name": booked['Name'],
                    "CNIC": booked['CNIC'],
                    "Outstanding": f"PKR {outstanding:,.2f}"
                })
                found = True
                
    if found:
        st.dataframe(pd.DataFrame(data), hide_index=True)
    else:
        st.success("No outstanding customers.")


def check_for_checkouts():
    st.header("📅 Today's Check-Outs")
    today = date.today()
    found = False
    data = []
    
    for name, d in rooms.items():
        booked = d.get("Booked-To")
        if booked:
            try:
                checkout_date = date.fromisoformat(booked["Check-Out"])
                if checkout_date == today:
                    data.append({
                        "Room": name,
                        "Name": booked['Name'],
                        "CNIC": booked['CNIC'],
                        "Outstanding": f"PKR {float(booked.get('Outstanding', 0) or 0):,.2f}"
                    })
                    found = True
            except:
                pass
                
    if found:
        st.dataframe(pd.DataFrame(data), hide_index=True)
    else:
        st.success("No check-outs today.")


def check_balance():
    """Shows the true hotel balance and transaction history."""
    earnings = load_json(EARNINGS_FILE)
    
    st.header("💰 Hotel Balance & Financial History")
    
    current_balance = earnings.get('balance', 0.0)
    
    if current_balance >= 0:
        st.metric(label="CURRENT HOTEL BALANCE", value=f"PKR {current_balance:,.2f}", delta="Profit")
    else:
        st.metric(label="CURRENT HOTEL BALANCE", value=f"PKR {current_balance:,.2f}", delta="Debt/Loss", delta_color="inverse")

    # Display History
    history = earnings.get('history', [])
    if history:
        st.subheader("Transaction History")
        
        # Prepare data for display
        df = pd.DataFrame(history)
        df = df.sort_values(by='date', ascending=False)
        df['amount'] = df['amount'].apply(lambda x: f"{'+' if x >= 0 else '-'}{abs(x):,.2f}")
        df['running_balance'] = df['running_balance'].apply(lambda x: f"PKR {x:,.2f}")
        df['date'] = df['date'].str.split(' ').str[0]
        
        df_display = df[['date', 'description', 'amount', 'running_balance']]
        df_display.columns = ['Date', 'Description', 'Amount', 'Running Balance']
        
        st.dataframe(df_display, hide_index=True)
        
        # Basic Visualization of Balance Trend (Optional)
        st.subheader("Balance Trend")
        df_plot = pd.DataFrame(history)
        df_plot['date'] = pd.to_datetime(df_plot['date']).dt.date
        df_plot['balance'] = df_plot['running_balance']
        
        st.line_chart(df_plot, x='date', y='balance')
        
    else:
        st.info("No financial transactions recorded yet.")


def handle_early_checkout():
    """
    Handles guest early check-out, calculating refunds or outstanding payments 
    based on the actual stay duration.
    """
    st.header("🏃 Early Check-Out & Settlement")
    
    cnic = st.text_input("Enter Guest CNIC", key="early_checkout_cnic")
    
    if st.button("Find Booking", key="find_early_checkout_btn"):
        st.session_state.checkout_bookings = [
            (name, d) for name, d in rooms.items()
            if d.get("Booked-To") and d["Booked-To"].get("CNIC") == cnic
        ]
        st.rerun()

    if "checkout_bookings" in st.session_state and st.session_state.checkout_bookings:
        
        # Display bookings and select one to proceed
        options = [
            f"{name} (Check-in: {d['Booked-To']['Check-in']})" 
            for name, d in st.session_state.checkout_bookings
        ]
        selected_option = st.selectbox("Select Room to Check Out Early", options)
        
        if selected_option:
            room_name = selected_option.split(" (Check-in:")[0]
            room = rooms[room_name]
            booking = room['Booked-To']

            # --- FINANCIAL CALCULATION ---
            fmt = "%Y-%m-%d"
            check_in_date = datetime.strptime(booking['Check-in'], fmt).date()
            today = date.today()
            
            # Days stayed (inclusive of check-in, exclusive of check-out)
            days_stayed = (today - check_in_date).days
            if days_stayed < 1: days_stayed = 1 
            
            daily_rate = float(booking['Daily Rate'])
            amount_paid = float(booking['Paid'])
            room_id = room['id']

            actual_bill = days_stayed * daily_rate
            
            st.subheader(f"Summary for {room_name}")
            st.markdown(f"- **Days Stayed:** {days_stayed} (until today)")
            st.markdown(f"- **Actual Bill:** PKR {actual_bill:,.2f}")
            st.markdown(f"- **Amount Paid:** PKR {amount_paid:,.2f}")
            
            refund_or_due = amount_paid - actual_bill
            
            if refund_or_due > 0:
                # REFUND DUE (Overpaid)
                st.warning(f"⚠️ REFUND DUE: Guest is owed PKR {refund_or_due:,.2f}")
                
                if st.button("Process Refund & Check Out", key="confirm_refund_checkout"):
                    # Log negative transaction (money leaving the hotel balance)
                    log_transaction(-refund_or_due, f"REFUND: Early Checkout {room_name}", room_id)
                    
                    # Finalize Checkout
                    room['Booked-To'] = None
                    room['available'] = True
                    save_json(ROOMS_FILE, rooms)
                    
                    
                    st.session_state.pop("checkout_bookings", None)
                    st.session_state.pop("early_checkout_cnic", None)
                    st.rerun()
                    st.success(f"Checkout complete for {room_name}. Refund recorded.")
            elif refund_or_due < 0:
                # OUTSTANDING DUE (Underpaid)
                due_amount = abs(refund_or_due)
                st.error(f"❌ OUTSTANDING DUE: Guest owes PKR {due_amount:,.2f}")
                
                payment = st.number_input("Amount Received Now:", min_value=0.0, max_value=due_amount, key="checkout_payment")
                
                if st.button("Receive Payment & Check Out", key="confirm_due_checkout"):
                    if payment > 0:
                        # Log income transaction
                        log_transaction(payment, f"INCOME: Checkout Settlement {room_name}", room_id)

                    # Finalize Checkout
                    room['Booked-To'] = None
                    room['available'] = True
                    save_json(ROOMS_FILE, rooms)
                    
                    st.success(f"Checkout complete for {room_name}. Payment recorded.")
                    st.session_state.pop("checkout_bookings", None)
                    st.session_state.pop("early_checkout_cnic", None)
                    st.rerun()
            else:
                # ACCOUNTS SETTLED EXACTLY
                st.success("Accounts are settled exactly.")
                if st.button("Finalize Check Out", key="confirm_final_checkout"):
                    room['Booked-To'] = None
                    room['available'] = True
                    save_json(ROOMS_FILE, rooms)
                    
                    st.success(f"Checkout complete for {room_name}.")
                    st.session_state.pop("checkout_bookings", None)
                    st.session_state.pop("early_checkout_cnic", None)
                    st.rerun()
    else:
        st.info("Enter a CNIC to start an early check-out.")


def update_booking():
    """Allows updating the check-out date and recalculating the bill."""
    st.header("🔄 Update Booking Dates")
    
    cnic = st.text_input("Enter CNIC to update booking", key="update_cnic")

    if st.button("Find Booking for Update", key="find_update_btn"):
        st.session_state.update_bookings = [
            (name, d) for name, d in rooms.items()
            if d.get("Booked-To") and d["Booked-To"].get("CNIC") == cnic
        ]
        st.rerun()
        
    if "update_bookings" in st.session_state and st.session_state.update_bookings:
        
        options = [f"{name} (Check-out: {d['Booked-To']['Check-Out']})" for name, d in st.session_state.update_bookings]
        selected_option = st.selectbox("Select Room to Update", options)

        if selected_option:
            room_name = selected_option.split(" (Check-out:")[0]
            room = rooms[room_name]
            booking = room['Booked-To']
            
            # Display current details
            st.info(f"Current Check-out: {booking['Check-Out']} | Total Price: PKR {booking['Total Price']:,.2f}")
            
            # Input for new date
            try:
                current_checkout_date = datetime.strptime(booking['Check-Out'], "%Y-%m-%d").date()
                check_in_date = datetime.strptime(booking['Check-in'], "%Y-%m-%d").date()
            except ValueError:
                st.error("Invalid date format found in existing booking.")
                return

            new_checkout = st.date_input(
                "Select New Check-out Date",
                value=current_checkout_date,
                min_value=check_in_date + timedelta(days=1),
                key="new_checkout_date"
            )

            if st.button("Confirm Date Update", key="confirm_update_btn"):
                new_checkout_str = new_checkout.isoformat()
                
                # Recalculate duration and price
                new_days = (new_checkout - check_in_date).days
                daily_rate = float(booking['Daily Rate'])
                paid_already = float(booking['Paid'])
                
                new_total_price = round(new_days * daily_rate, 2)
                new_outstanding = round(new_total_price - paid_already, 2)
                
                # --- Update the Data ---
                booking['Check-Out'] = new_checkout_str
                booking['Days'] = new_days
                booking['Total Price'] = new_total_price
                booking['Outstanding'] = new_outstanding

                save_json(ROOMS_FILE, rooms)

                st.success("Booking date successfully updated!")
                st.markdown(f"**New Check-out:** {new_checkout_str}")
                st.markdown(f"**New Total Price:** PKR {new_total_price:,.2f}")
                st.markdown(f"**Remaining Outstanding:** PKR {new_outstanding:,.2f}")
                st.session_state.pop("update_bookings", None)
                st.session_state.pop("update_cnic", None)
                st.rerun()

    else:
        st.info("Enter a CNIC to find and update a booking.")

def log_transaction(amount, description, room_id, transaction_type="INCOME"):
    """
    Updates the global balance and records history in earnings.json.
    amount: Positive for Income, Negative for Refunds/Expenses.
    transaction_type: 'INCOME', 'EXPENSE', 'REFUND'
    """
    earnings = load_json(EARNINGS_FILE)
    
    amount = float(amount)
    earnings['balance'] += amount # Subtracts if amount is negative
    
    # Create Record
    record = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "description": description,
        "amount": round(amount, 2), # Round for currency
        "room_id": room_id,
        "type": transaction_type,
        "running_balance": round(earnings['balance'], 2)
    }
    
    earnings['history'].append(record)
    save_json(EARNINGS_FILE, earnings)
    
    icon = "💸" if transaction_type == "INCOME" else "🛑" if transaction_type == "EXPENSE" else "↩️"
    st.toast(f"Transaction Logged: {description} | Amount: Rs. {abs(amount):,.2f}", icon=icon)


# --- NEW CORE FUNCTIONS FOR EXPENSES ---

def generate_expense_ledger(expense_type, description, total_amount, items):
    """Generates a detailed expense ledger in Markdown format for download."""
    
    ledger_content = io.StringIO()
    
    # Header
    ledger_content.write(f"# Hotel Expense Ledger Report\n\n")
    ledger_content.write(f"--- \n")
    ledger_content.write(f"## 🧾 Expense Details\n")
    ledger_content.write(f"| Detail | Value |\n")
    ledger_content.write(f"| :--- | :--- |\n")
    ledger_content.write(f"| **Date Logged** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |\n")
    ledger_content.write(f"| **Category** | {expense_type} |\n")
    ledger_content.write(f"| **Description** | {description} |\n")
    ledger_content.write(f"| **Total Amount** | PKR {total_amount:,.2f} |\n")
    ledger_content.write(f"\n\n")

    # Itemized Breakdown
    if items:
        df_items = pd.DataFrame(items)
        
        ledger_content.write("## 📋 Itemized Breakdown\n")
        
        # Calculate column widths for clean formatting
        item_col_width = max(len(str(item['item'])) for item in items) + 4
        cost_col_width = max(len(f"{item['cost_per_unit']:,.2f}") for item in items) + 12
        qty_col_width = max(len(str(item['quantity'])) for item in items) + 5
        subtotal_col_width = max(len(f"{item['subtotal']:,.2f}") for item in items) + 10
        
        # Write table header
        ledger_content.write(f"| {'Item/Service':<{item_col_width}} | {'Cost Per Unit':<{cost_col_width}} | {'Quantity':<{qty_col_width}} | {'Subtotal (PKR)':<{subtotal_col_width}} |\n")
        ledger_content.write(f"| {':---':<{item_col_width}} | {':---:':<{cost_col_width}} | {':---:':<{qty_col_width}} | {':---:':<{subtotal_col_width}} |\n")

        # Write rows
        for item in items:
            ledger_content.write(
                f"| {item['item']:<{item_col_width}} "
                f"| {f'PKR {item['cost_per_unit']:,.2f}':<{cost_col_width}} "
                f"| {item['quantity']:<{qty_col_width}} "
                f"| {item['subtotal']:<{subtotal_col_width},.2f} |\n"
            )
            
        ledger_content.write("\n")
        ledger_content.write(f"**BREAKDOWN TOTAL:** PKR {df_items['subtotal'].sum():,.2f}\n")
    
    st.download_button(
        label="⬇️ Download Expense Ledger (.md)",
        data=ledger_content.getvalue(),
        file_name=f"Expense_Ledger_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
        mime="text/markdown"
    )

def handle_expenses():
    """
    Manages hotel expenses, logs them, and allows generation of a detailed expense ledger.
    """
    st.header("💸 Hotel Expenses Ledger")
    
    # --- 1. Log New Expense ---
    st.subheader("Log New Expense")

    expense_type = st.selectbox(
        "Expense Category",
        ["Salaries", "Maintenance/Repair", "Renovation/Upgrade", "Supplies", "Utilities", "Other"],
        key="expense_category"
    )
    
    description = st.text_area("Detailed Description (e.g., 'May 2024 staff salaries')", key="expense_desc")
    total_amount = st.number_input("Total Expense Amount (PKR)", min_value=0.01, key="expense_amount")
    
    # --- Input for detailed itemized expenses (for the ledger file) ---
    st.markdown("---")
    st.subheader("Itemized Breakdown (Optional for Ledger)")
    
    # Using session state to hold items
    if 'expense_items' not in st.session_state:
        st.session_state.expense_items = []
        
    item_name = st.text_input("Item/Service Name", key="item_name")
    item_cost = st.number_input("Cost Per Unit (PKR)", min_value=0.0, key="item_cost")
    item_quantity = st.number_input("Quantity/Rooms Affected", min_value=1, step=1, key="item_qty")
    
    if st.button("Add Item to Breakdown"):
        if item_name and item_cost > 0 and item_quantity > 0:
            st.session_state.expense_items.append({
                "item": item_name,
                "cost_per_unit": item_cost,
                "quantity": item_quantity,
                "subtotal": round(item_cost * item_quantity, 2)
            })
            # Clear input fields by popping their state keys
            st.session_state.pop("item_name")
            st.session_state.pop("item_cost")
            st.session_state.pop("item_qty")
            st.rerun() # Rerun to clear inputs and display table

    if st.session_state.expense_items:
        st.subheader("Current Breakdown")
        df_items = pd.DataFrame(st.session_state.expense_items)
        df_items_display = df_items.rename(columns={
            'item': 'Item/Service',
            'cost_per_unit': 'Cost Per Unit (PKR)',
            'quantity': 'Quantity',
            'subtotal': 'Subtotal (PKR)'
        })
        st.dataframe(df_items_display, hide_index=True)
        
        # Calculate total of itemized breakdown
        breakdown_total = df_items['subtotal'].sum()
        st.markdown(f"**Breakdown Total:** PKR {breakdown_total:,.2f}")
        
        if st.button("Clear Breakdown"):
            st.session_state.pop("expense_items", None)
            st.rerun()

    
    st.markdown("---")
    if st.button("Confirm and Log Expense", key="log_expense_btn"):
        if not description or total_amount <= 0:
            st.error("Please enter a description and a valid amount.")
        else:
            # Log the expense as a NEGATIVE amount
            log_transaction(
                amount=-total_amount, 
                description=f"EXPENSE: {expense_type} - {description}", 
                room_id="N/A", # Expenses are usually not room-specific
                transaction_type="EXPENSE"
            )
            st.success(f"Expense of PKR {total_amount:,.2f} logged successfully.")
            
            # --- Generate Downloadable Ledger File ---
            if st.session_state.expense_items:
                generate_expense_ledger(
                    expense_type, 
                    description, 
                    total_amount, 
                    st.session_state.expense_items
                )
            
            # Clear all inputs for a clean slate
            st.session_state.pop("expense_items", None)
            st.session_state.pop("expense_category", None)
            st.session_state.pop("expense_desc", None)
            st.session_state.pop("expense_amount", None)
            st.rerun()
            
            
# --- Sidebar Menu ---
st.sidebar.title("🏨 Hotel System Menu")
choice = st.sidebar.radio(
    "Select Action",
    [
        "Show Available Rooms",
        "Book a Room",
        "Update Booking",
        "Check Balance",
        "Check Out",
        "Early Check-Out",
        "Pay Dues",
        "See Outstanding Customers",
        "Today's Check-Outs",
        "Manage Expenses"
    ]
)

# --- Page Routing ---
if choice == "Show Available Rooms":
    show_available_rooms()
elif choice == "Book a Room":
    book_room()
elif choice == "Update Booking":
    update_booking()
elif choice == "Check Balance":
    check_balance()
elif choice == "Check Out":
    check_out()
elif choice == "Pay Dues":
    pay_amnt()
elif choice == "See Outstanding Customers":
    see_outstanding()
elif choice == "Today's Check-Outs":
    check_for_checkouts()
elif choice == "Early Check-Out":
    handle_early_checkout()
elif choice == "Manage Expenses":
    handle_expenses()

# Final save ensures all changes made are persisted
save_json(ROOMS_FILE, rooms)