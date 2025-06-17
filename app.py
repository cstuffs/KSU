from flask import Flask, render_template, request, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from collections import OrderedDict
from io import BytesIO
from openpyxl import Workbook
from models import db, Team, User, Order, OrderItem
from datetime import datetime, timedelta
import json
import os

# === Flask App Setup ===
app = Flask(__name__)
app.secret_key = 'your-secret-key'

# === Database Configuration ===
import os

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'instance', 'local.db')

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# === Flask-Login Setup ===
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# === Models ===
class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    budget = db.Column(db.Float, default=100.0)
    remaining_budget = db.Column(db.Float, default=100.0)  # ✅ Add this line
    members = db.relationship('User', backref='team', lazy=True)
    orders = db.relationship('Order', backref='team', lazy=True)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    orders = db.relationship('Order', backref='user', lazy=True)

    def get_id(self):
        return str(self.id)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    item_name = db.Column(db.String, nullable=False)
    option_name = db.Column(db.String, nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Float, nullable=False, default=0.0)

# === Login Loader ===
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# === Create Tables Automatically ===
db_created = False

# === Example Home Route ===
@app.route('/')
def home():
    return "Welcome to the Team Ordering App!"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        raw_team = request.form.get('team_name', '').strip()
        raw_name = request.form.get('member_name', '').strip()

        team_input = raw_team.lower()
        member_input = raw_name.lower()

        # Get matching team
        team = Team.query.filter(db.func.lower(Team.name) == team_input).first()
        if not team:
            return f"Team '{raw_team}' not found.", 403

        # Get matching user in that team
        user = User.query.filter(
            db.func.lower(User.name) == member_input,
            User.team_id == team.id
        ).first()

        if not user:
            return f"User '{raw_name}' not found on team '{raw_team}'.", 403

        # Save user session
        login_user(user)
        session['team'] = team.name
        session['member_name'] = user.name

        # Admin rules
        if team.name == "KSU Football":
            if user.name == "Scott Trausch":
                session['admin_as_football'] = False  # Full admin
                return redirect(url_for('admin_dashboard'))
            else:
                session['admin_as_football'] = True  # Limited admin
                return redirect(url_for('admin_dashboard'))

        # All others: standard user
        session['admin_as_football'] = False
        return redirect(url_for('submit_order'))

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('login'))

@app.route('/order', methods=['GET'])
@login_required
def submit_order():
    # Redirect full admin to dashboard
    if current_user.name == 'admin' and not session.get('admin_as_football'):
        return redirect(url_for('admin_dashboard'))

    if request.args.get("new") == "1":
        session.pop("last_order_form", None)

    form_data = session.get('last_order_form', {})

    # ✅ Get team from database
    team = current_user.team
    if not team:
        return "Team not found for current user.", 400

    team_budget = team.budget
    remaining_budget = team.remaining_budget

    # ✅ Week range string
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday() + 1) if today.weekday() != 6 else today
    end_of_week = start_of_week + timedelta(days=6)
    week_range_str = f"{start_of_week.strftime('%-m/%-d/%y')} - {end_of_week.strftime('%-m/%-d/%y')}"

    # ✅ Load structured menu
    with open('structured_menu.json', 'r') as f:
        grouped_menu = json.load(f, object_pairs_hook=OrderedDict)

    return render_template("order.html",
                           current_user=current_user,
                           session=session,
                           grouped_menu=grouped_menu,
                           user_budget=team_budget,
                           remaining_budget=remaining_budget,
                           week_range=week_range_str,
                           form_data=form_data)

@app.route('/add_to_order', methods=['POST'])
@login_required
def add_to_order():
    form_data = request.form.to_dict()

    cleaned_form = {}

    for key in form_data:
        if key.startswith("qty_"):
            qty_str = form_data[key].strip()
            if qty_str.isdigit() and int(qty_str) > 0:
                cleaned_form[key] = qty_str

        elif key.startswith("meta_"):
            suffix = key[5:]
            qty_key = f"qty_{suffix}"
            qty_str = form_data.get(qty_key, "").strip()
            if qty_str.isdigit() and int(qty_str) > 0:
                cleaned_form[key] = form_data[key]

    # Store cleaned form data in session for next step (review/submit)
    session['last_order_form'] = cleaned_form

    if form_data.get("action") == "review":
        return redirect(url_for('review_order'))
    else:
        return redirect(url_for('submit_order'))

@app.route('/order/edit', methods=['POST'])
@login_required
def order_form_edit():
    if current_user.name == 'admin' and not session.get("admin_as_football"):
        return redirect(url_for('admin_dashboard'))

    form_data = request.form
    selected_items = []

    for key in form_data:
        if key.startswith("meta_"):
            suffix = key[5:]
            qty_key = f"qty_{suffix}"
            qty_str = form_data.get(qty_key, "").strip()
            if qty_str.isdigit() and int(qty_str) > 0:
                try:
                    item_name, option_name, price = form_data[key].split("|||")
                    selected_items.append({
                        "name": item_name,
                        "option": option_name,
                        "price": float(price),
                        "quantity": int(qty_str),
                        "meta_key": key,
                        "qty_key": qty_key
                    })
                except Exception:
                    continue

    return render_template("order_edit.html", selected_items=selected_items)

@app.route('/order/review', methods=['GET', 'POST'])
@login_required
def review_order():
    # Get team from current user
    team = current_user.team
    if not team:
        return "Team not found for current user.", 400

    team_budget = team.budget

    # Week range string
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday() + 1) if today.weekday() != 6 else today
    end_of_week = start_of_week + timedelta(days=6)
    week_range_str = f"{start_of_week.strftime('%-m/%-d/%y')} - {end_of_week.strftime('%-m/%-d/%y')}"

    # Load last order form data from session
    form_data = session.get('last_order_form', {})
    session['last_order_form'] = form_data

    items = []
    total = 0.0

    for key in form_data:
        if key.startswith("meta_"):
            suffix = key[5:]
            qty_key = f"qty_{suffix}"
            qty_str = form_data.get(qty_key, "0").strip()

            if qty_str.isdigit() and int(qty_str) > 0:
                quantity = int(qty_str)
                try:
                    item_name, option_name, price = form_data[key].split("|||")
                    price = float(price)
                    subtotal = price * quantity
                    total += subtotal
                    items.append({
                        "name": item_name,
                        "option": option_name,
                        "price": price,
                        "quantity": quantity,
                        "subtotal": subtotal
                    })
                except:
                    continue

    return render_template("order_review.html",
                           items=items,
                           total=total,
                           user_budget=team_budget,
                           remaining_budget=round(team.remaining_budget - total, 2),
                           week_range=week_range_str,
                           form_data=form_data)

@app.route('/order/submit', methods=['POST'])
@login_required
def finalize_order():
    form_data = session.get('last_order_form', {})
    items = []
    total = 0.0

    for key in form_data:
        if key.startswith("meta_"):
            suffix = key[5:]
            qty_key = f"qty_{suffix}"
            qty_str = form_data.get(qty_key, "0").strip()

            if qty_str.isdigit() and int(qty_str) > 0:
                try:
                    item_name, option_name, price = form_data[key].split("|||")
                    price = float(price)
                    quantity = int(qty_str)
                    total += price * quantity
                    items.append({
                        "name": item_name,
                        "option": option_name,
                        "price": price,
                        "quantity": quantity
                    })
                except:
                    continue

    # ✅ Save to DB if there are items
    if items:
        now = datetime.now()
        new_order = Order(
            user_id=current_user.id,
            team_id=current_user.team_id,
            date=now.date(),
            time=now.time()
        )
        db.session.add(new_order)
        db.session.flush()  # Get new_order.id for OrderItem foreign keys

        for item in items:
            db.session.add(OrderItem(
                order_id=new_order.id,
                item_name=item["name"],
                option_name=item["option"],
                quantity=item["quantity"],
                price=item["price"]
            ))

        team = current_user.team
        team.remaining_budget -= total
        db.session.commit()

    # ✅ Clear form session after saving
    session.pop('last_order_form', None)

    return redirect(url_for('submit_order'))

@app.route('/admin')
@login_required
def admin_dashboard():
    # Access control: allow full admin or KSU Football limited admin
    if not (session.get('admin_as_football') or session.get('member_name') == "Scott Trausch"):
        return "Access Denied", 403

    # Query all team names from the database
    all_teams = [team.name for team in Team.query.order_by(Team.name).all()]

    # Week range string
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday() + 1) if today.weekday() != 6 else today
    end_of_week = start_of_week + timedelta(days=6)
    week_range_str = f"{start_of_week.strftime('%-m/%-d/%y')} - {end_of_week.strftime('%-m/%-d/%y')}"

    return render_template('admin_dashboard.html', teams=all_teams, week_range=week_range_str)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard_view():
    if current_user.id != 'admin' and not session.get('admin_as_football'):
        return "Access Denied", 403

    # ✅ Load from users.json to include *all* teams
    with open('users.json') as f:
        users_data = json.load(f, object_pairs_hook=OrderedDict)

    teams = list(users_data.keys())  # include all teams, even empty

    return render_template("admin_dashboard.html", teams=teams)

@app.route('/admin/produce_hyvee')
@login_required
def admin_produce_hyvee():
    if not (session.get('admin_as_football') or session.get('member_name') == "Scott Trausch"):
        return "Access Denied", 403

    # Load structured menu to get Produce + Hyvee items
    with open("structured_menu.json", "r") as f:
        menu = json.load(f)

    produce_items = set(menu.get("Produce", {}).keys())
    hyvee_items = set(menu.get("Hyvee", {}).keys())
    valid_items = produce_items | hyvee_items

    # Define current week range
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday() + 1) if today.weekday() != 6 else today
    end_of_week = start_of_week + timedelta(days=6)

    # Query all relevant orders within the week
    matching_orders = []
    orders = Order.query.filter(Order.date >= start_of_week.date(), Order.date <= end_of_week.date()).all()

    for order in orders:
        team_name = order.team.name
        for item in order.items:
            if item.item_name in valid_items:
                matching_orders.append((
                    order.date.strftime("%Y-%m-%d"),
                    team_name,
                    item.item_name,
                    item.quantity
                ))

    week_range = f"{start_of_week.strftime('%-m/%-d/%y')} - {end_of_week.strftime('%-m/%-d/%y')}"

    return render_template("admin_produce_hyvee.html", orders=matching_orders, week_range=week_range)

@app.route('/admin/produce_hyvee/export')
@login_required
def export_produce_hyvee_excel():
    if not (session.get('admin_as_football') or session.get('member_name') == "Scott Trausch"):
        return "Access Denied", 403

    # Define current week range
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday() + 1) if today.weekday() != 6 else today
    end_of_week = start_of_week + timedelta(days=6)

    # Load valid Produce and Hyvee item names
    with open("structured_menu.json", "r") as f:
        menu = json.load(f)

    produce_items = set(menu.get("Produce", {}).keys())
    hyvee_items = set(menu.get("Hyvee", {}).keys())
    valid_items = produce_items | hyvee_items

    # Create Excel workbook
    wb_out = Workbook()
    ws_out = wb_out.active
    ws_out.title = "Produce & Hyvee"
    ws_out.append(["Date", "Team", "Item", "Quantity"])

    # Query orders within week
    orders = Order.query.filter(Order.date >= start_of_week.date(), Order.date <= end_of_week.date()).all()

    for order in orders:
        team_name = order.team.name
        order_date_str = order.date.strftime("%Y-%m-%d")
        for item in order.items:
            if item.item_name in valid_items:
                ws_out.append([order_date_str, team_name, item.item_name, item.quantity])

    # Create downloadable Excel file
    output = BytesIO()
    wb_out.save(output)
    output.seek(0)

    filename = f"Produce_Hyvee_Orders_{start_of_week.strftime('%Y%m%d')}.xlsx"
    return send_file(output,
                     download_name=filename,
                     as_attachment=True,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route('/admin/weekly_summary')
@login_required
def admin_weekly_summary():
    if not (session.get('admin_as_football') or session.get('member_name') == "Scott Trausch"):
        return "Access Denied", 403
    
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday() + 1) if today.weekday() != 6 else today
    end_of_week = start_of_week + timedelta(days=6)
    week_range_str = f"{start_of_week.strftime('%-m/%-d/%y')} - {end_of_week.strftime('%-m/%-d/%y')}"

    all_orders = []

    orders = Order.query.filter(Order.date >= start_of_week.date(), Order.date <= end_of_week.date()).all()

    for order in orders:
        team_name = order.team.name
        for item in order.items:
            item_full = f"{item.item_name} - {item.option_name}".strip(" -")
            all_orders.append({
                "date": order.date.strftime("%-m/%-d/%y"),
                "team": team_name,
                "item": item_full,
                "quantity": item.quantity
            })

    return render_template(
        "weekly_summary.html",
        week_range=week_range_str,
        orders=all_orders,
        datetime=datetime,   # ✅ add this
        timedelta=timedelta
    )

@app.route('/admin/weekly_summary/export')
@login_required
def export_weekly_summary_excel():
    if not (session.get('admin_as_football') or session.get('member_name') == "Scott Trausch"):
        return "Access Denied", 403

    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday() + 1) if today.weekday() != 6 else today
    end_of_week = start_of_week + timedelta(days=6)

    orders = Order.query.filter(Order.date >= start_of_week.date(), Order.date <= end_of_week.date()).all()

    wb_out = Workbook()
    ws_out = wb_out.active
    ws_out.title = "Weekly Summary"
    ws_out.append(["Date", "Team", "Item", "Quantity"])

    for order in orders:
        team_name = order.team.name
        order_date = order.date.strftime("%Y-%m-%d")
        for item in order.items:
            item_full = f"{item.item_name} - {item.option_name}".strip(" -")
            ws_out.append([order_date, team_name, item_full, item.quantity])

    output = BytesIO()
    wb_out.save(output)
    output.seek(0)

    filename = f"Full_Weekly_Orders_{start_of_week.strftime('%Y%m%d')}.xlsx"
    return send_file(output,
                     download_name=filename,
                     as_attachment=True,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route('/admin/football_order')
@login_required
def admin_football_order():
    if not (session.get('admin_as_football') or session.get('member_name') == "Scott Trausch"):
        return "Access Denied", 403

    # Only full admin simulates KSU Football ordering (without logging in as them)
    session['admin_as_football'] = True
    return redirect(url_for('submit_order'))

@app.route('/admin/team/<team_name>')
@login_required
def view_team_orders(team_name):
    if not (session.get('admin_as_football') or session.get('member_name') == "Scott Trausch"):
        return "Access Denied", 403

    team = Team.query.filter_by(name=team_name).first()
    if not team:
        return f"Team '{team_name}' not found", 404

    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday() + 1) if today.weekday() != 6 else today
    end_of_week = start_of_week + timedelta(days=6)
    week_range_str = f"{start_of_week.strftime('%-m/%-d/%y')} - {end_of_week.strftime('%-m/%-d/%y')}"

    # Load prices from structured_menu.json
    with open('structured_menu.json', 'r') as f:
        full_menu = json.load(f)

    price_lookup = {
        f"{item_name}|||{opt['name']}": opt["price"]
        for group in full_menu.values()
        for item_name, options in group.items()
        for opt in options
    }

    # Init structures
    weekly_orders_by_member = {}
    all_totals = {}
    total_cost = 0.0

    for user in team.members:
        member_orders = []
        member_total = 0.0

        for order in user.orders:
            for item in order.items:
                key = f"{item.item_name}|||{item.option_name}"
                price = price_lookup.get(key, 0.0)
                quantity = item.quantity or 0
                subtotal = quantity * price

                # Weekly filter
                if start_of_week.date() <= order.date <= end_of_week.date():
                    member_orders.append({
                        "date": order.date.strftime("%Y-%m-%d"),
                        "time": order.time.strftime("%I:%M %p"),
                        "item": f"{item.item_name} - {item.option_name}".strip(" -"),
                        "quantity": quantity,
                        "price": f"${price:.2f}",
                        "subtotal": f"${subtotal:.2f}"
                    })
                    member_total += subtotal
                    total_cost += subtotal

                # Accumulate full-year totals
                full_item_name = f"{item.item_name} - {item.option_name}".strip(" -")
                if full_item_name not in all_totals:
                    all_totals[full_item_name] = {"qty": 0, "total_cost": 0.0}

                all_totals[full_item_name]["qty"] += quantity
                all_totals[full_item_name]["total_cost"] += quantity * price

        if member_orders:
            weekly_orders_by_member[user.name] = {
                "orders": member_orders,
                "total": member_total
            }

    # Team budget info
    team_budget = team.budget
    remaining_budget = round(team.remaining_budget, 2)

    return render_template("team_orders.html",
                           team_name=team_name,
                           week_range=week_range_str,
                           weekly_orders_by_member=weekly_orders_by_member,
                           total_orders=all_totals,
                           total_cost=total_cost,
                           user_budget=team_budget,
                           remaining_budget=remaining_budget)

@app.route('/admin/user/<user_name>')
@login_required
def view_user_file(user_name):
    if not (session.get('admin_as_football') or session.get('member_name') == "Scott Trausch"):
        return "Access Denied", 403

    # Find the user by name
    user = User.query.filter_by(name=user_name).first()
    if not user:
        return f"No user found with name '{user_name}'", 404

    current_week = datetime.now().isocalendar()[1]
    weekly_orders = []
    item_totals = {}

    for order in user.orders:
        order_week = order.date.isocalendar()[1]

        for item in order.items:
            item_key = f"{item.item_name} - {item.option_name}".strip(" -")

            # Running total of all orders (lifetime)
            if item_key not in item_totals:
                item_totals[item_key] = 0
            item_totals[item_key] += item.quantity

            # Weekly orders (current week only)
            if order_week == current_week:
                weekly_orders.append({
                    "date": order.date.strftime("%Y-%m-%d"),
                    "item": item_key,
                    "quantity": item.quantity
                })

    total_orders = [{"item": name, "quantity": qty} for name, qty in item_totals.items()]

    return render_template("user_orders.html",
                           user_name=user_name,
                           weekly_orders=weekly_orders,
                           total_orders=total_orders)

@app.route('/admin/weekly_totals')
@login_required
def weekly_totals():
    if not (session.get('admin_as_football') or session.get('member_name') == "Scott Trausch"):
        return "Access Denied", 403

    # Load structured menu and build price lookup
    with open("structured_menu.json", "r") as f:
        menu = json.load(f)

    price_lookup = {
        f"{item}|||{opt['name']}": opt["price"]
        for group in menu.values()
        for item, options in group.items()
        for opt in options
    }

    def get_week_number(date):
        year_start = datetime(date.year, 1, 1).date()
        if year_start.weekday() != 6:
            year_start -= timedelta(days=year_start.weekday() + 1)
        delta = date - year_start
        return (delta.days // 7) + 1

    yearly_totals_by_week = {}
    all_years = set()

    orders = Order.query.join(Team).all()
    for order in orders:
        team_name = order.team.name
        year = order.date.year
        week = get_week_number(order.date)

        all_years.add(year)

        if week < 1 or week > 52:
            continue

        yearly_totals_by_week.setdefault(year, {}).setdefault(week, {})

        for item in order.items:
            key = f"{item.item_name}|||{item.option_name}"
            price = price_lookup.get(key, 0.0)
            subtotal = item.quantity * price
            current = yearly_totals_by_week[year][week].get(team_name, 0.0)
            yearly_totals_by_week[year][week][team_name] = current + subtotal

    # Make sure every week/year has all teams
    all_team_names = [team.name for team in Team.query.order_by(Team.name).all()]
    for year in all_years:
        for week in range(1, 53):
            yearly_totals_by_week.setdefault(year, {}).setdefault(week, {})
            for team in all_team_names:
                yearly_totals_by_week[year][week].setdefault(team, 0.0)

    return render_template(
        "weekly_totals.html",
        yearly_totals_by_week=yearly_totals_by_week,
        users=all_team_names,
        years=sorted(all_years),
        datetime=datetime,
        timedelta=timedelta
    )

@app.route('/admin/all_orders')
@login_required
def all_orders():
    if not (session.get('admin_as_football') or session.get('member_name') == "Scott Trausch"):
        return "Access Denied", 403

    all_orders = []

    all_db_orders = Order.query.join(User).join(Team).all()

    for order in all_db_orders:
        order_date = order.date
        order_time = order.time
        member_name = order.user.name
        team_name = order.team.name
        year = order_date.year
        week_num = (order_date - datetime(2025, 1, 1).date()).days // 7 + 1

        for item in order.items:
            all_orders.append({
                "date": order_date.strftime("%Y-%m-%d"),
                "time": order_time.strftime("%I:%M %p"),
                "week": week_num,
                "year": year,
                "team": team_name,
                "member": member_name,
                "item": f"{item.item_name} - {item.option_name}".strip(" -"),
                "quantity": item.quantity
            })

    return render_template("all_orders.html", orders=all_orders)

@app.route('/admin/budgets', methods=['GET', 'POST'])
@login_required
def manage_budgets():
    if not (session.get('admin_as_football') or session.get('member_name') == "Scott Trausch"):
        return "Access Denied", 403

    teams = Team.query.order_by(Team.name).all()

    if request.method == 'POST':
        if 'reset' in request.form:
            # Reset remaining budgets
            for team in teams:
                team.remaining_budget = team.budget
            db.session.commit()
            return render_template("manage_budgets.html", team_budgets={team.name: team.budget for team in teams}, message="✅ All remaining budgets reset.")
        else:
            # Update budgets
            for team in teams:
                new_value = request.form.get(team.name)
                if new_value:
                    try:
                        team.budget = float(new_value)
                    except ValueError:
                        continue
            db.session.commit()
            return redirect(url_for('manage_budgets'))

    team_budgets = {team.name: team.budget for team in teams}
    return render_template("manage_budgets.html", team_budgets=team_budgets)

@app.route('/admin/edit_menu', methods=['GET', 'POST'])
@login_required
def edit_menu():
    if not (session.get('admin_as_football') or session.get('member_name') == "Scott Trausch"):
        return "Access Denied", 403

    menu_path = 'structured_menu.json'

    if request.method == 'POST':
        form = request.form
        updated_menu = OrderedDict()

        group_names = [key.split('[')[1].split(']')[0] for key in form.keys() if key.startswith("group_names[")]
        group_names = list(OrderedDict.fromkeys(group_names))

        for group in group_names:
            item_names = form.getlist(f'group_names[{group}][item_names][]')
            group_data = OrderedDict()
            for item_name in item_names:
                item_name = item_name.strip()
                if not item_name:
                    continue
                options = form.getlist(f'options[{item_name}][]')
                prices = form.getlist(f'prices[{item_name}][]')
                if not options or not prices or len(options) != len(prices):
                    continue
                item_options = []
                for opt, price_str in zip(options, prices):
                    opt = opt.strip()
                    try:
                        price = float(price_str)
                        if opt:
                            item_options.append({ "name": opt, "price": price })
                    except ValueError:
                        continue
                if item_options:
                    group_data[item_name] = item_options
            if group_data:
                updated_menu[group] = group_data

        with open(menu_path, 'w') as f:
            json.dump(updated_menu, f, indent=2)
        return redirect(url_for('edit_menu'))

    with open(menu_path, 'r') as f:
        grouped_menu = json.load(f, object_pairs_hook=OrderedDict)
    return render_template('edit_menu_fixed.html', grouped_menu=grouped_menu)

@app.route('/admin/edit_users', methods=['GET', 'POST'])
@login_required
def edit_users():
    if not (session.get('admin_as_football') or session.get('member_name') == "Scott Trausch"):
        return "Access Denied", 403

    if request.method == 'POST':
        team_names = request.form.getlist('team_names[]')
        members_list = request.form.getlist('members[]')

        for team_name, members_raw in zip(team_names, members_list):
            team_name = team_name.strip()
            if not team_name:
                continue

            team = Team.query.filter_by(name=team_name).first()
            if not team:
                team = Team(name=team_name, budget=100.0)
                db.session.add(team)
                db.session.flush()

            # Clear and re-add users
            User.query.filter_by(team_id=team.id).delete()
            members = [m.strip() for m in members_raw.splitlines() if m.strip()]
            for member_name in members:
                db.session.add(User(name=member_name, team_id=team.id))

        db.session.commit()
        return redirect(url_for('admin_dashboard'))

    # Display current team/user structure
    teams = Team.query.order_by(Team.name).all()
    users_by_team = OrderedDict()
    for team in teams:
        users_by_team[team.name] = [user.name for user in team.members]

    return render_template("edit_users.html", users=users_by_team)

@app.route('/init_db')
def init_db():
    from models import db  # if you're using a separate models.py
    db.create_all()
    return "✅ Database initialized!"

# === Run the App ===
if __name__ == '__main__':
    app.run(debug=True, port=5001)
