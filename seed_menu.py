import json
from app import app, db
from models import MenuGroup, MenuItem, MenuOption
from collections import OrderedDict

def seed_menu():
    with app.app_context():
        with open("structured_menu.json", "r") as f:
            menu = json.load(f, object_pairs_hook=OrderedDict)

        for group_name, group_items in menu.items():
            group = MenuGroup(name=group_name)
            db.session.add(group)
            db.session.flush()

            for item_name, options in group_items.items():
                item = MenuItem(name=item_name, group_id=group.id)
                db.session.add(item)
                db.session.flush()

                for option in options:
                    db.session.add(MenuOption(
                        name=option["name"],
                        price=option["price"],
                        item_id=item.id
                    ))

        db.session.commit()
        print("✅ Menu seeded to database")
