# vesper-mongodb

MongoDB integration for Vesper via PyMongo. Provides a database handle injectable into services and IPC commands for common CRUD operations.

---

## Install

```bash
pip install vesper-mongodb
```

Requires a running MongoDB instance. [MongoDB Community Edition](https://www.mongodb.com/try/download/community) is free for local development.

---

## Setup

```python
from vesper import App
from vesper_mongodb import MongoPlugin

app = App(
    title="My App",
    frontend="dist/index.html",
    plugins=[MongoPlugin(uri="mongodb://localhost:27017", database="mydb")],
    root_module=AppModule,
)
```

---

## JavaScript API

Add the SDK:

```toml
[plugins]
mongodb = "vesper-mongodb"
```

```bash
vesper sync-sdk
```

```html
<script src="vesper.js"></script>
<script src="vesper-mongo.js"></script>
```

### Methods

```js
// Find multiple documents
const users = await vesper.mongo.find("users")
const admins = await vesper.mongo.find("users", { role: "admin" })

// Find one document
const user = await vesper.mongo.findOne("users", { email: "alice@example.com" })
// null if not found

// Insert one document
const result = await vesper.mongo.insertOne("users", {
    name: "Alice",
    email: "alice@example.com",
    role: "user",
})
// result: { inserted_id: "507f1f77bcf86cd799439011" }

// Insert multiple documents
const result = await vesper.mongo.insertMany("users", [
    { name: "Bob" },
    { name: "Carol" },
])
// result: { inserted_ids: ["...", "..."] }

// Update one document
await vesper.mongo.updateOne(
    "users",
    { email: "alice@example.com" },
    { $set: { role: "admin" } }
)

// Update multiple documents
await vesper.mongo.updateMany(
    "users",
    { role: "user" },
    { $set: { verified: false } }
)

// Delete one document
await vesper.mongo.deleteOne("users", { email: "alice@example.com" })

// Delete multiple documents
await vesper.mongo.deleteMany("users", { role: "guest" })

// Count documents
const count = await vesper.mongo.count("users")
const adminCount = await vesper.mongo.count("users", { role: "admin" })
```

---

## Python injection (MongoDatabase)

```python
from vesper import Injectable, Controller, command
from vesper_mongodb import MongoDatabase

@Injectable()
class UserService:
    def __init__(self, db: MongoDatabase):
        self.collection = db["users"]

    def list(self) -> list[dict]:
        return list(self.collection.find({}, {"_id": 0}))

    def create(self, name: str, email: str) -> dict:
        doc = {"name": name, "email": email}
        result = self.collection.insert_one(doc)
        return {"id": str(result.inserted_id), "name": name, "email": email}

    def find_by_email(self, email: str) -> dict | None:
        doc = self.collection.find_one({"email": email})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
```

`MongoDatabase` is a `pymongo.database.Database` instance. Use standard PyMongo methods on it.

---

## ObjectId serialization

MongoDB documents contain `ObjectId` values in `_id` fields. Vesper automatically converts `ObjectId` to string in all IPC responses — you never need to handle this manually.

```js
const user = await vesper.mongo.findOne("users", { name: "Alice" })
// user._id is a string, not an ObjectId object
console.log(user._id)   // "507f1f77bcf86cd799439011"
```

When querying by `_id` from JavaScript, pass the string ID:

```python
from bson import ObjectId

@app.command
def get_user(id: str) -> dict | None:
    db = ...   # MongoDatabase instance
    doc = db["users"].find_one({"_id": ObjectId(id)})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc
```

---

## IPC command names

| Command | Args | Returns |
|---|---|---|
| `mongo:find` | `collection, filter?` | `list[dict]` |
| `mongo:find_one` | `collection, filter?` | `dict \| null` |
| `mongo:insert_one` | `collection, document` | `{ inserted_id }` |
| `mongo:insert_many` | `collection, documents` | `{ inserted_ids }` |
| `mongo:update_one` | `collection, filter, update` | `{ matched, modified }` |
| `mongo:update_many` | `collection, filter, update` | `{ matched, modified }` |
| `mongo:delete_one` | `collection, filter` | `{ deleted }` |
| `mongo:delete_many` | `collection, filter` | `{ deleted }` |
| `mongo:count` | `collection, filter?` | `int` |

---

## Indexes

Create indexes in Python before `app.run()` or in an `@app.on("loaded")` hook:

```python
@app.on("loaded")
def create_indexes():
    from vesper.core.module import Container
    from vesper_mongodb import MongoDatabase
    db = Container._global.get(MongoDatabase)
    db["users"].create_index("email", unique=True)
    db["posts"].create_index([("created_at", -1)])
```

---

## Connection string options

```python
# With authentication
MongoPlugin(
    uri="mongodb://username:password@host:27017",
    database="mydb",
)

# MongoDB Atlas
MongoPlugin(
    uri="mongodb+srv://user:pass@cluster.mongodb.net",
    database="mydb",
)

# Replica set
MongoPlugin(
    uri="mongodb://host1:27017,host2:27017/?replicaSet=rs0",
    database="mydb",
)
```
