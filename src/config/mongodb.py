from pymongo.mongo_client import MongoClient

def iniciarDB(uri):
    client = MongoClient(uri)
    mongo = client['audiosDB']
    return mongo
