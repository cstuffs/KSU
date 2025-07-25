from models import db, Team, User
from app import app

def seed_db():
    with app.app_context():
        db.drop_all()
        db.create_all()

        football = Team(name="KSU Football", budget=100.0)
        baseball = Team(name="KSU Baseball", budget=100.0)
        track = Team(name="KSU Track", budget=100.0)

        db.session.add_all([football, baseball, track])
        db.session.commit()

        user1 = User(name="Scott Trausch", team_id=football.id)
        user2 = User(name="Cody S", team_id=football.id)
        user3 = User(name="Cody Stufflebean", team_id=baseball.id)
        user4 = User(name="Belle Stufflebean", team_id=track.id)

        db.session.add_all([user1, user2, user3, user4])
        db.session.commit()
        print("✅ Seeded database.")
