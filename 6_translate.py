from mongodbDriver import MongoDBManager
import requests


def main():
    db_manager = MongoDBManager(
        host="localhost",
        port=27017,
        username="admin",
        password="password",
        database_name="mastodon-analysis",
    )

    url = "http://localhost:5000/translate"

    try:
        db_manager.connect()

        db = db_manager.get_database()
        collection = db["instances"]

        documents = list(
            collection.find(
                {"trending_posts_status": "SUCCESS"}, {"name", "original_content"}
            )
        )

        # Iterate through each document in the collection
        for document in documents:
            original_content = []
            translate_status = "SUCCESS"
            for status in document["original_content"]:
                if status["detected_language"] == "en":
                    original_content.append(status)
                else:
                    libretranslate_translation = ""
                    libretranslate_round_trip = ""
                    data = {
                        "q": status["content"],
                        "source": status[
                            "detected_language"
                        ],  # FIXME: change no->nb, zh-CN->zh
                        "target": "en",
                    }

                    response = requests.post(url, json=data)
                    if response.status_code == 200:
                        libretranslate_translation = response.json()["translatedText"]
                        # FIXME: if libretranslate_translation between 10 200 token, continue
                        round_trip_data = {
                            "q": libretranslate_translation,
                            "source": "en",
                            "target": status["detected_language"],
                        }
                        round_trip_response = requests.post(url, json=round_trip_data)
                        if round_trip_response.status_code == 200:
                            libretranslate_round_trip = round_trip_response.json()[
                                "translatedText"
                            ]
                        else:
                            translate_status = "ERROR_ROUNDTRIP"
                            libretranslate_round_trip = round_trip_response.text
                            print("Error:", round_trip_response.text)
                    else:
                        translate_status = "ERROR_TRANSLATE"
                        libretranslate_translation = response.text
                        print("Error:", response.text)

                    original_content.append(
                        {
                            "content": status["content"],
                            "language": status["language"],
                            "detected_language": status["detected_language"],
                            "libretranslate_translation": libretranslate_translation,
                            "libretranslate_round_trip": libretranslate_round_trip,
                        }
                    )

            # FIXME: if original_content is empty, it means there were posts available,
            # but after translation they were ignored (probably ja,th, cz)
            # so I need to update the doocument as if it was INSUFFICIENT_DATA 
            # here is a sample output:
            
                # "trending_posts_status" : "INSUFFICIENT_DATA",
                # "original_content" : [

                # ]

            # else the following update

            # Update the document with the modified `original_content`
            collection.update_one(
                {"_id": document["_id"]},  # Filter by document ID
                {
                    "$set": {
                        "original_content": original_content,  # Update the field
                        "translate_status": translate_status,  # Add the new field
                    }
                },
            )

    finally:
        # Close the connection
        db_manager.close()


if __name__ == "__main__":
    main()
