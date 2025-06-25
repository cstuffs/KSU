from flask_login import UserMixin
from extensions import db

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    budget = db.Column(db.Float, default=100.0)
    remaining_budget = db.Column(db.Float, default=100.0)
    members = db.relationship('User', backref='team', lazy=True, passive_deletes=True)
    orders = db.relationship('Order', backref='team', lazy=True)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id', ondelete='SET NULL'), nullable=True)
    is_enabled = db.Column(db.Boolean, default=True)  # ✅ Soft-delete flag
    orders = db.relationship('Order', backref='user', lazy=True)

    def get_id(self):
        return str(self.id)

    @property
    def is_active(self):
        # Used by Flask-Login to determine if user can log in
        return self.is_enabled

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

class MenuOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    price = db.Column(db.Float, nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('menu_item.id'), nullable=False)

class MenuGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    items = db.relationship('MenuItem', back_populates='group', cascade="all, delete-orphan")  # ✅

class MenuItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('menu_group.id'))
    case_size = db.Column(db.Integer, default=1)
    reorder_point = db.Column(db.Integer, default=0)

    group = db.relationship('MenuGroup', back_populates='items')  # ✅
    options = db.relationship('MenuOption', backref='item', cascade='all, delete-orphan')

