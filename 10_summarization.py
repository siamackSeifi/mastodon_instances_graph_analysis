from mongodbDriver import MongoDBManager
from transformers import pipeline
from bert_score import score as bert_score
import evaluate
from nltk.tokenize import word_tokenize

# from keybert import KeyBERT
# from sentence_transformers import SentenceTransformer
from transformers import logging

logging.set_verbosity_error()


# Load summarization pipeline
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

# Initialize the SentenceTransformer model for KeyBERT
# embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
# kw_model = KeyBERT(embedding_model)


def calculate_metrics(references, candidates):
    try:
        # Calculate BERTScore with FacebookAI/roberta-large
        P, R, F1 = bert_score(
            candidates, references, model_type="roberta-large", lang="en"#, verbose=True
        )
        bertscore_results = {
            "precision": P.mean().item(),
            "recall": R.mean().item(),
            "f1": F1.mean().item()
        }

        # Calculate ROUGE using the new `evaluate` library
        rouge_metric = evaluate.load("rouge")
        rouge_scores = rouge_metric.compute(predictions=candidates, references=references)

        # # Extract keywords using KeyBERT
        # keywords = kw_model.extract_keywords(candidates[0], top_n=5)
        # print("\nExtracted Keywords:")
        # print(keywords)
        return {
            "bertscore": bertscore_results,
            "rouge": rouge_scores
        }
    except Exception as e:
        print(f"An error occurred while calculating metrics: {e}")
        return None


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
                    "summarization_status": "NOT_STARTED"
                },
                {"name", "original_content"},
            )
        )

        for document in documents:
            try:
                intermediate_summaries = []
                for status in document["original_content"][:10]:
                    # Perform summarization
                    if status["detected_language"] == "en":
                        text = status["content"]
                    else:
                        text = status["libretranslate_translation"]

                    token_count = len(word_tokenize(text))
                    if token_count > 1023:
                        print("\n\n\n","*"*65)
                        print(f"text higher than 1023 tokens, doc ID: {document['_id']}")
                        print("*"*65, "\n\n\n")
                        continue
                    elif token_count > 100:
                        summary = summarizer(
                            text, max_length=75, min_length=25, do_sample=False
                        )[0]["summary_text"]
                    else:
                        summary = text
                    intermediate_summaries.append(summary)

                # Step 2: Concatenate all intermediate summaries
                concatenated_summary = "\n".join(intermediate_summaries)

                # Step 3: Generate final summary with default parameters
                if len(word_tokenize(concatenated_summary)) > 150:
                    final_summary = summarizer(
                        concatenated_summary, max_length=142, min_length=56, do_sample=False
                    )[0]["summary_text"]
                else:
                    final_summary = concatenated_summary

                # Step 4: Calculate BERTScore, ROUGE, and Keywords
                reference_text = [concatenated_summary]  # Original reference
                summary_text = [final_summary]  # Generated summary
                metrics = calculate_metrics(reference_text, summary_text)

                if metrics is None:
                    raise Exception("Metrics calculation failed.")

                # update document
                collection.update_one(
                    {"_id": document["_id"]},
                    {
                        "$set": {
                            "summarization_status": "COMPLETED",
                            "summarization_text": final_summary,
                            "summarization_bertscore": metrics["bertscore"],
                            "summarization_rouge": metrics["rouge"],
                        }
                    },
                )
            except Exception as e:
                print(f"An error occurred for document {document['_id']}: {e}")
                collection.update_one(
                    {"_id": document["_id"]},
                    {"$set": {"summarization_status": "ERROR"}},
                )
    finally:
        # Close the connection
        db_manager.close()


if __name__ == "__main__":
    main()
