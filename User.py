import json
from Mongo_Access import DB_Client
class User:
    """Helper class for accessing Mongo db"""

    def __init__(self, user_id : str,client : DB_Client):
        self.user_id = user_id
        self.udata = None
        self.client_instance = client
        self.client = self.client_instance.clt

    def user_exists(self) -> bool:
        """Check if user exists ie if user has completed OAuth flow then he should exist"""
        auth = self.client['TBot_DB']['auth']
        print({"user.user_id" : self.user_id})
        usr = auth.find_one({"user.user_id" : self.user_id})
        print(usr)
        if usr is not None:
            return True
        return False

    def delete_user(self) -> bool:
        """Delete user from db"""
        try:
            auth = self.client['TBot_DB']['auth']
            query = auth.find_one_and_delete({"user.user_id" : self.user_id})
            if query is not None:
                return True
            return False
        except Exception as e:
            return False
    def load_user_data(self) -> bool:
        """Load user data from Mongo DB"""
        try:
            if self.user_exists():
                auth = self.client['TBot_DB']['auth']
                usr = auth.find_one({"user.user_id" : self.user_id})
                if usr is not None:
                    self.udata = usr
                    del self.udata['_id']
                    return True
                return False
            return False
        except Exception as e:
            return False
    def update_user_data(self,data) -> bool:
        """Update user data in Mongo DB"""
        try:
            data = { "user" : data }
            auth = self.client['TBot_DB']['auth']
            keys = list(data.keys())
            uid = str(keys[0])
            result = auth.update_one(
                {"user.user_id" : self.user_id},  # Filter: documents that have uid field
                {"$set": data},
                upsert=True
            )
            if result is not None:
                return True
            return False
        except Exception as e:
            print(str(e))

