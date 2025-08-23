from pymongo import MongoClient


class MongoDBManager:
    def __init__(
        self,
        host="localhost",
        port=27017,
        username=None,
        password=None,
        database_name=None,
    ):
        """
        Initialize the MongoDBManager with connection parameters.

        Args:
            host (str): MongoDB server hostname or IP (default: localhost).
            port (int): MongoDB server port (default: 27017).
            username (str): MongoDB username (default: None).
            password (str): MongoDB password (default: None).
            database_name (str): Default database name (default: None).
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database_name = database_name
        self.client = None
        self.database = None

    def connect(self):
        """Create a connection to MongoDB."""
        try:
            if self.username and self.password:
                uri = f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/"
            else:
                uri = f"mongodb://{self.host}:{self.port}/"

            self.client = MongoClient(uri)
            print("MongoDB connection established.")

            if self.database_name:
                self.database = self.client[self.database_name]
        except Exception as e:
            print(f"Failed to connect to MongoDB: {e}")
            raise

    def get_database(self, database_name=None):
        """
        Get a database instance.

        Args:
            database_name (str): Name of the database to retrieve (default: None).

        Returns:
            Database: A MongoDB database instance.
        """
        if not self.client:
            raise Exception("MongoDB client is not connected. Call `connect()` first.")

        return self.client[database_name or self.database_name]

    def close(self):
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()
            print("MongoDB connection closed.")
            self.client = None
            self.database = None
        else:
            print("No active MongoDB connection to close.")
