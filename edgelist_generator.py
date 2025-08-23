from mongodbDriver import MongoDBManager


def main():
    db_manager = MongoDBManager(
        host="localhost",
        port=27017,
        username="admin",
        password="password",
        database_name="mastodon-analysis",
    )

    try:
        db_manager.connect()

        db = db_manager.get_database()
        collection = db["instances"]
        edgelist = set()

        # Step 1: Fetch all documents with 'name' and 'valid_neighbors'
        documents = list(
            collection.find(
                {"trending_posts_status": "SUCCESS"},
                {"name": 1, "valid_neighbors": 1},
            )
        )

        # Step 2: Build a set of valid names
        valid_names = set(doc["name"] for doc in documents)

        # Iterate through each document in the collection
        for document in documents:
            source = document.get("name")
            neighbors = document.get("valid_neighbors", [])

            filtered_neighbors = [
                neighbor for neighbor in neighbors if neighbor in valid_names
            ]

            for neighbor in filtered_neighbors:
                # Skip if source and neighbor are the same (e.g. self-loop)
                if source == neighbor:
                    continue

                # Store edges as sorted tuples to ensure uniqueness
                edge = tuple(sorted((source, neighbor)))
                edgelist.add(edge)
    finally:
        # Close the connection
        db_manager.close()

    edgelist = list(edgelist)

    with open("edgelist_content.txt", "w") as file:
        for edge in edgelist:
            file.write(f"{edge[0]} {edge[1]}\n")


if __name__ == "__main__":
    main()

