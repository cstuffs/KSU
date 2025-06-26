from app import app, db
from models import MenuGroup, MenuItem, MenuOption

with app.app_context():
    groups = MenuGroup.query.order_by(MenuGroup.id).all()
    for group_index, group in enumerate(groups):
        group.position = group_index

        items = MenuItem.query.filter_by(group_id=group.id).order_by(MenuItem.id).all()
        for item_index, item in enumerate(items):
            item.position = item_index

            options = MenuOption.query.filter_by(item_id=item.id).order_by(MenuOption.id).all()
            for opt_index, opt in enumerate(options):
                opt.position = opt_index

    db.session.commit()
    print("✅ Backfilled all missing .position fields.")
