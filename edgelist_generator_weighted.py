from mongodbDriver import MongoDBManager
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


def calculate_weighted_edgelist(
    input_file, output_file, mongo_uri="mongodb://admin:password@localhost:27017/"
):
    # Connect to MongoDB
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

        # Fetch all documents with name and sbert_embedding
        documents = list(
            collection.find(
                {
                    "trending_posts_status": "SUCCESS",
                },
                {"name": 1, "sbert_embedding": 1},
            )
        )
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Close the connection
        db_manager.close()

    # Create a dictionary mapping names to embeddings
    name_to_embedding = {
        doc["name"]: np.array(doc["sbert_embedding"])
        for doc in documents
        if "sbert_embedding" in doc
    }

    # Open input and output files
    with open(input_file, "r") as infile, open(output_file, "w") as outfile:
        for line in infile:
            try:
                # Extract name pairs from each line
                name1, name2 = line.strip().split()

                # Check if both names exist in the embedding dictionary
                if name1 in name_to_embedding and name2 in name_to_embedding:
                    embedding1 = name_to_embedding[name1].reshape(1, -1)
                    embedding2 = name_to_embedding[name2].reshape(1, -1)

                    # Calculate cosine similarity
                    sim_score = cosine_similarity(embedding1, embedding2)[0][0]

                    # Write to the output file
                    outfile.write(f"{name1} {name2} {sim_score:.4f}\n")
                else:
                    print(
                        f"Missing embedding for: {name1} or {name2}. Skipping this pair."
                    )
            except Exception as e:
                print(f"Error processing line '{line.strip()}': {e}")
                continue

    print(f"Weighted edgelist written to: {output_file}")


if __name__ == "__main__":
    # Input and output file paths
    input_file = "edgelist_content.txt"
    output_file = "edgelist_content_weighted.txt"

    # Generate the weighted edgelist
    calculate_weighted_edgelist(input_file, output_file)
