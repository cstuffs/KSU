from flask_login import UserMixin
from app import db  # ✅ Correct import

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    budget = db.Column(db.Float, default=100.0)
    remaining_budget = db.Column(db.Float, default=100.0)
    members = db.relationship('User', backref='team', lazy=True)
    orders = db.relationship('Order', backref='team', lazy=True)

class User(UserMixin, db.Model):  # ✅ Include UserMixin
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    orders = db.relationship('Order', backref='user', lazy=True)

    def get_id(self):
        return str(self.id)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    item_name = db.Column(db.String, nullable=False)
    option_name = db.Column(db.String, nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False, default=0.0)
