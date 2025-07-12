# tasks.py
from app import app, db
from models import Order, User, Team
from app import get_week_number
from datetime import datetime
from zoneinfo import ZoneInfo
from io import BytesIO
from openpyxl import Workbook
import smtplib
from email.message import EmailMessage

CDT = ZoneInfo("America/Chicago")

def email_all_orders():
    with app.app_context():
        print("[Scheduled Job] Generating all orders Excel…")

        wb = Workbook()
        ws = wb.active
        ws.title = "All Orders"
        ws.append(["Date", "Time", "Week", "Year", "Team", "Member", "Item", "Quantity"])

        all_db_orders = Order.query.join(User).join(Team).all()

        for order in all_db_orders:
            order_date = order.date
            order_time = order.time
            member_name = order.user.name
            team_name = order.team.name
            year = order_date.year
            week_num = get_week_number(order_date)

            for item in order.items:
                ws.append([
                    order_date.strftime("%Y-%m-%d"),
                    order_time.strftime("%I:%M %p"),
                    week_num,
                    year,
                    team_name,
                    member_name,
                    f"{item.item_name} - {item.option_name}".strip(" -"),
                    item.quantity
                ])

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        msg = EmailMessage()
        msg['Subject'] = "Weekly All Orders Report"
        msg['From'] = "codystufflebean@gmail.com"
        msg['To'] = "strausch@kstatesports.com"
        msg.set_content("Attached is the weekly all-orders Excel report.")

        msg.add_attachment(output.read(),
                           maintype="application",
                           subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           filename="All_Orders.xlsx")

        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login("codystufflebean@gmail.com", "dbmblqvczexojevy")
                smtp.send_message(msg)
            print("[Scheduled Job] Email sent to Scott.")
        except Exception as e:
            print(f"[Scheduled Job] Failed to send email: {e}")
