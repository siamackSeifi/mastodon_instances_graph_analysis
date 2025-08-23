from mongodbDriver import MongoDBManager

from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from nltk.translate.meteor_score import meteor_score, single_meteor_score
from nltk.tokenize import word_tokenize
from sentence_transformers import SentenceTransformer, util
from collections import defaultdict
import numpy as np


# Initialize the LaBSE model
model = SentenceTransformer("sentence-transformers/LaBSE")

# import nltk

# nltk.download('wordnet')
# nltk.download('punkt')
# nltk.download('punkt_tab')


def calculate_translation_scores(source_text, translation, back_translation):
    # Tokenize the sentences (BLEU in nltk requires tokenized inputs)
    source_tokens = word_tokenize(source_text)
    back_translation_tokens = word_tokenize(back_translation)

    # Use a smoothing function to handle brevity penalties in short sentences
    smoothing_function = SmoothingFunction().method1

    # Calculate BLEU score
    bleu_score = sentence_bleu(
        [source_tokens],  # Reference (source text)
        back_translation_tokens,  # Hypothesis (back translation)
        smoothing_function=smoothing_function,
    )

    # Calculate METEOR score
    meteor = single_meteor_score(source_tokens, back_translation_tokens)

    # Encode the sentences to get their embeddings
    source_embedding = model.encode(source_text, convert_to_tensor=True)
    translation_embedding = model.encode(translation, convert_to_tensor=True)
    back_translation_embedding = model.encode(back_translation, convert_to_tensor=True)

    # Compute cosine similarity between the source and translation embeddings
    similarity = util.pytorch_cos_sim(source_embedding, translation_embedding).item()
    similarity2 = util.pytorch_cos_sim(
        source_embedding, back_translation_embedding
    ).item()

    # Return all scores
    return {
        "bleu": round(bleu_score, 4),
        "meteor": round(meteor, 4),
        "LaBSE_CoSim": round(similarity, 4),
        "LaBSE_CoSim_back": round(similarity2, 4),
    }


def main():
    db_manager = MongoDBManager(
        host="localhost",
        port=27017,
        username="admin",
        password="password",
        database_name="mastodon-analysis",
    )

    # # Dictionary to store scores grouped by language
    # language_scores = defaultdict(lambda: defaultdict(list))

    try:
        db_manager.connect()

        db = db_manager.get_database()
        collection = db["instances"]

        documents = list(
            collection.find(
                {
                    "translate_status": "SUCCESS",
                    # "original_content.detected_language": {"$ne": "en"},
                },
                {"name", "original_content"},
            )
        )
        # Iterate through each document in the collection
        counter = 0
        for document in documents:
            original_content = []
            for status in document["original_content"]:
                if status["detected_language"] != "en":
                    status.update(
                        calculate_translation_scores(
                            status["content"],
                            status["libretranslate_translation"],
                            status["libretranslate_round_trip"],
                        )
                    )

                original_content.append(status)

            collection.update_one(
                {"_id": document["_id"]},  # Filter by document ID
                {
                    "$set": {
                        "original_content": original_content,  # Update the field
                    }
                },
            )
            counter += 1
            print(counter)

    finally:
        # Close the connection
        db_manager.close()

    # # Calculate and display statistics using NumPy
    # for language, metrics in language_scores.items():
    #     print(f"\nLanguage: {language}")
    #     for metric, values in metrics.items():
    #         min_score = np.min(values)
    #         mean_score = np.mean(values)
    #         print(f"  {metric}: Min = {min_score:.4f}, Mean = {mean_score:.4f}")


if __name__ == "__main__":
    main()
