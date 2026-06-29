class MongoDatabase:
    """Type marker for DI injection of the pymongo Database instance."""
    pass


def _serialize(value):
    """Recursively convert ObjectIds and other non-JSON types to strings."""
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    # ObjectId check without a hard bson import — works with any pymongo version
    if type(value).__name__ == "ObjectId":
        return str(value)
    return value
