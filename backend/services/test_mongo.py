import sys
try:
    import pymongo
    c = pymongo.MongoClient('mongodb://localhost:27017/aziza', serverSelectionTimeoutMS=2000)
    c.server_info()
    print('Connected successfully!')
except Exception as e:
    print('Error connecting:', str(e))
