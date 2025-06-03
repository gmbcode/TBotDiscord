# I0hkgKV3UfplfCn6
# mongodb+srv://anonymousunknownb:I0hkgKV3UfplfCn6@tbot-cluster.y2augrv.mongodb.net/
from pymongo import MongoClient
from dotenv import dotenv_values
config = dotenv_values(".env")


class DB_Client:
    def __init__(self):
        print("Client generated")
        self.url = config["MONGO_DB_CLUSTER_URL"]
        self.username = config["MONGO_DB_ADMIN_USERNAME"]
        self.password = config["MONGO_DB_ADMIN_PASSWORD"]
        self.clt = MongoClient(f'mongodb+srv://{self.username}:{self.password}@{self.url}')
    def __del__(self):
        self.clt.close()

