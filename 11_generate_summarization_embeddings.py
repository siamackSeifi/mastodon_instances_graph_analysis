from mongodbDriver import MongoDBManager

from sentence_transformers import SentenceTransformer
# from transformers import AutoTokenizer, AutoModel
# import torch

sbert_model = SentenceTransformer("all-MiniLM-L6-v2")
# roberta_tokenizer = AutoTokenizer.from_pretrained("roberta-large")
# roberta_model = AutoModel.from_pretrained("roberta-large")

# from transformers import logging

# logging.set_verbosity_error()

# def mean_pooling(model_output, attention_mask):
#     token_embeddings = model_output.last_hidden_state  # [batch_size, seq_len, hidden_dim]
#     input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size())
#     sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, dim=1)
#     sum_mask = torch.clamp(input_mask_expanded.sum(dim=1), min=1e-9)
#     return sum_embeddings / sum_mask


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

        documents = list(
            collection.find(
                {
                    "trending_posts_status": "SUCCESS",
                    "summarization_status": "COMPLETED",
                },
                {"name", "summarization_text"},
            )
        )

        for document in documents:
            try:
                summarization_text = document.get("summarization_text", "")
                if not summarization_text:
                    print(
                        f"Skipping document {document['_id']} with empty summarization_text."
                    )
                    continue

                # Generate SBERT embedding
                sbert_embedding = sbert_model.encode(
                    summarization_text, convert_to_tensor=True
                ).tolist()

                # Update document with embeddings
                collection.update_one(
                    {"_id": document["_id"]},
                    {
                        "$set": {
                            "sbert_embedding": sbert_embedding,
                        }
                    },
                )

            except Exception as e:
                print(f"An error occurred for document {document['_id']}: {e}")
                continue

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Close the connection
        db_manager.close()


if __name__ == "__main__":
    main()
