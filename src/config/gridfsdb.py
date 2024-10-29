import gridfs
from pymongo import MongoClient

def iniciar_grid_fs(uri):
    client = MongoClient(uri)
    mongo = client['audiosDB']
    grid_fs = gridfs.GridFS(mongo)
    return grid_fs