# 🏨 Hotel Management System (Streamlit)

A complete hotel management & revenue tracking system built using **Python + Streamlit**.  
This system allows staff to manage bookings, check-ins, check-outs, dues, early settlements, revenue logging, and more.

---

## 📌 Features

### ✔ Room Management
- Add / update rooms
- Show available rooms
- Floor-wise filtering
- Real-time availability status

### ✔ Booking System
- Multiselect room booking
- Date-range picker (check-in & check-out)
- Automatic day calculation
- Seasonal discount system (July–Dec 15% off)
- Partial or full payments
- Outstanding dues tracking

### ✔ Payment & Accounting
- All payments logged into `earnings.json`
- Running hotel balance tracking
- Revenue, dues, and refunds fully recorded
- Visual graph of balance trend

### ✔ Check-Out System
- Standard checkout (requires dues = 0)
- Early checkout with:
  - Refund calculation
  - Additional dues calculation
  - Automatic transaction logging

### ✔ Admin Tools
- View all outstanding customers
- Today's checkout list
