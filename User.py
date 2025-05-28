import json


class User:
    """Helper class for accessing JSON db"""

    def __init__(self, user_id : str):
        self.user_id = user_id
        self.udata = None

    def user_exists(self) -> bool:
        """Check if user exists ie if user has completed OAuth flow then he should exist"""
        db_current = json.load(open('udb.json', 'r'))
        if self.user_id in db_current:
            return True
        return False

    def delete_user(self) -> bool:
        """Delete user from db"""
        try:
            db_current = json.load(open('udb.json', 'r'))
            del db_current[self.user_id]
            with open('udb.json', 'w') as f:
                json.dump(db_current, f, indent=2, default=str)
            return True
        except Exception as e:
            return False
    def load_user_data(self) -> bool:
        """Load user data from json file"""
        try:
            if self.user_exists():
                db_current = json.load(open('udb.json', 'r'))
                self.udata = db_current[self.user_id]
                return True
            return False
        except Exception as e:
            return False
