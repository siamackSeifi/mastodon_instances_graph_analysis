from mongodbDriver import MongoDBManager

import langdetect
import fasttext
import gcld3
import numpy as np

# Initialize fastText model (ensure you have downloaded the 'lid.176.bin' model)
ft_model = fasttext.load_model("lid.176.bin")

# Initialize GCLD3 detector
gcld3_detector = gcld3.NNetLanguageIdentifier(min_num_bytes=0, max_num_bytes=1000)

# Acceptable confidence threshold
ACCEPTABLE_CONFIDENCE = 0.7


# Initialize variables to track confidence scores for each model
langdetect_confidences = []
ft_confidences = []
gcld3_confidences = []


# Function to detect language using langdetect
def detect_language_langdetect(text):
    try:
        detected_langs = langdetect.detect_langs(text)
        top_language = max(detected_langs, key=lambda x: x.prob)
        return top_language.lang, top_language.prob
    except langdetect.lang_detect_exception.LangDetectException as e:
        return None, 0  # Return None and 0 for error


# Function to detect language using fastText
def detect_language_fasttext(text):
    # Remove newline characters from the text
    text = text.replace("\n", " ").replace("\r", "")

    predictions = ft_model.predict(text, k=2)  # Get top 2 predictions
    language_ft = predictions[0][0].replace("__label__", "")
    confidence_ft = predictions[1][0]
    return language_ft, confidence_ft


# Function to detect language using GCLD3
def detect_language_gcld3(text):
    result = gcld3_detector.FindLanguage(text)
    return result.language, result.probability


# Function to check if predictions and confidence are valid
def check_predictions(text):
    lang = "mismatched"
    mismatchFlag = 0
    confidenceFlag = 0
    # Get predictions and confidences from all models
    langdetect_lang, langdetect_conf = detect_language_langdetect(text)
    ft_lang, ft_conf = detect_language_fasttext(text)
    gcld3_lang, gcld3_conf = detect_language_gcld3(text)

    # Check if the predictions are the same
    if (
        langdetect_lang != ft_lang
        or langdetect_lang != gcld3_lang
        or ft_lang != gcld3_lang
    ):
        mismatchFlag = 1
        # print(f"langdetect={langdetect_lang}:{langdetect_conf}, fastText={ft_lang}:{ft_conf}, gcld3={gcld3_lang}:{gcld3_conf}")

        # Check if any confidence score is lower than acceptable when mismatch occurs
        if (
            langdetect_conf < ACCEPTABLE_CONFIDENCE
            or ft_conf < ACCEPTABLE_CONFIDENCE
            or gcld3_conf < ACCEPTABLE_CONFIDENCE
        ):
            confidenceFlag = 1
            print(
                f"Low confidence detected: langdetect={langdetect_conf}, fastText={ft_conf}, gcld3={gcld3_conf}"
            )
    else:
        lang = ft_lang

    # Track the confidence scores
    langdetect_confidences.append(langdetect_conf)
    ft_confidences.append(ft_conf)
    gcld3_confidences.append(gcld3_conf)

    return lang, mismatchFlag, confidenceFlag


def print_confidence_stats(model_name, confidences):
    # Convert confidences to a numpy array
    confidences_array = np.array(confidences)

    # Calculate min and mean using numpy
    print(
        f"{model_name} - Min confidence: {np.min(confidences_array):.2f}, Mean confidence: {np.mean(confidences_array):.2f}"
    )


def main():
    db_manager = MongoDBManager(
        host="localhost",
        port=27017,
        username="admin",
        password="password",
        database_name="mastodon-analysis",
    )

    try:
        totalCount = 0
        mismatchCount = 0
        confidenceCount = 0
        db_manager.connect()

        db = db_manager.get_database()
        collection = db["instances"]

        # Iterate through each document in the collection
        for document in collection.find(
            {"trending_posts_status": "SUCCESS"}, {"name", "original_content"}
        ):
            original_content = []
            for status in document["original_content"]:
                totalCount += 1
                lang, mismatch, confidence = check_predictions(status["content"])
                original_content.append(
                    {
                        "content": status["content"],
                        "language": status["language"],
                        "detected_language": lang,
                    }
                )
                mismatchCount += mismatch
                confidenceCount += confidence

            # Update the document with the modified `original_content`
            collection.update_one(
                {"_id": document["_id"]},  # Filter by document ID
                {"$set": {"original_content": original_content}}  # Update the field
            )

    finally:
        print("\n\n")
        # Close the connection
        db_manager.close()
        # Ensure there are confidence scores to avoid errors
        if langdetect_confidences:
            print_confidence_stats("Langdetect", langdetect_confidences)

        if ft_confidences:
            print_confidence_stats("FastText", ft_confidences)

        if gcld3_confidences:
            print_confidence_stats("GCLD3", gcld3_confidences)
        print("\n\n")
        print(f"totalCount: {totalCount}")
        print(
            f"mismatchCount: {mismatchCount} which equals to {(mismatchCount/totalCount):.2f}% of contents"
        )
        print(
            f"confidenceCount: {confidenceCount} which equals to {(confidenceCount/mismatchCount):.2f}% of mismatched contents"
        )


if __name__ == "__main__":
    main()
