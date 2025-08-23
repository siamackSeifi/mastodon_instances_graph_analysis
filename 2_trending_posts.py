import requests
from urllib.parse import urljoin
from html.parser import HTMLParser
from io import StringIO
import re
from nltk.tokenize import word_tokenize

from mongodbDriver import MongoDBManager

import signal


class TimeoutException(Exception):
    pass


class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, d):
        self.text.write(d)

    def get_data(self):
        return self.text.getvalue()


def _strip_tags(html):
    html = re.sub(r"</?br\s*/?>", "\n", html)
    html = re.sub(r"(</p>)", r"\n\1", html)
    s = HTMLStripper()
    s.feed(html)
    return s.get_data()


def _strip_custom_emojis(html, custom_emojis):
    for emoji in custom_emojis:
        shortcode = f":{emoji['shortcode']}:"
        html = html.replace(shortcode, "")
    return html


def text_validation(text):
    # Remove links
    text = re.sub(r"http\S+|www\.\S+", "", text)
    # Remove @tags (e.g., @someName)
    text = re.sub(r"@\w+", "", text)
    # Replace multiple spaces, tabs, and newlines with a single space
    text = re.sub(r"\s+", " ", text).strip()

    # Check if the word count is between 10 and 100
    # NOTE: This fails for chinese, japanese, and thai. Needs to be handled after translation.
    return 10 <= len(word_tokenize(text)) <= 200


def fetch_trending_tags(name):
    result = {"errors": [], "posts": []}  # Initialize result structure
    url = urljoin(f"https://{name}", "/api/v1/trends/statuses?limit=40")

    def timeout_handler(signum, frame):
        raise TimeoutException("The request timed out")

    signal.signal(signal.SIGALRM, timeout_handler)  # Set the timeout handler

    try:
        signal.alarm(10)  # Set a 10-second hard timeout
        response = requests.get(url, timeout=(5, 10))
        signal.alarm(0)  # Cancel the alarm after the request completes
        response.raise_for_status()  # Raise an exception for HTTP errors

        if not response.headers.get("Content-Type", "").startswith("application/json"):
            raise ValueError("Invalid Content-Type from the endpoint")

        data = response.json()
        if "error" in data:
            raise ValueError(f"Error from endpoint: {data['error_description']}")

        for item in data:
            custom_emojis = item.get("emojis", [])
            if item.get("reblog"):  # reblog (retweet)
                custom_emojis.extend(item["reblog"].get("emojis", []))
                content_html = item["reblog"].get("content", "")
                content = _strip_tags(_strip_custom_emojis(content_html, custom_emojis))
                language = item["reblog"].get("language", "")
            else:
                content_html = item.get("content", "")
                content = _strip_tags(_strip_custom_emojis(content_html, custom_emojis))
                language = item.get("language", "")

            if not text_validation(content):
                continue

            result["posts"].append({"content": content, "language": language})

    except TimeoutException:
        result["errors"].append({"error": "Request exceeded hard timeout limit"})
    except requests.exceptions.RequestException as e:
        result["errors"].append({"error": f"Request error: {str(e)}"})
    except ValueError as e:
        result["errors"].append({"error": str(e)})
    except Exception as e:
        result["errors"].append({"error": f"Unexpected error: {str(e)}"})
    finally:
        signal.alarm(0)  # Ensure the alarm is canceled in any case

    return result


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

        documents = collection.find({"trending_posts_status": "NOT_STARTED"}, {"name": 1})

        document_list = list(documents)
        if not document_list:
            print("All instances finished")
            return
        print(f"starting the round with {len(document_list)} instances./n/n")

        for doc in document_list:
            instance_name = doc.get("name")
            if not instance_name:
                continue
            try:
                result = fetch_trending_tags(instance_name)
                if result["errors"]:
                    collection.update_one(
                        {"_id": doc["_id"]},
                        {
                            "$set": {
                                "trending_posts_status": "ERROR",
                                "errors": result["errors"],
                            }
                        },
                    )
                else:
                    trending_posts_status = "SUCCESS"
                    if not result["posts"]:
                        trending_posts_status = "INSUFFICIENT_DATA"

                    collection.update_one(
                        {"_id": doc["_id"]},
                        {
                            "$set": {
                                "trending_posts_status": trending_posts_status,
                                "original_content": result["posts"]
                            }
                        },
                    )

            except Exception as e:
                print("process error")

    except Exception as e:
        print("error connecting to db")

    finally:
        db_manager.close()


if __name__ == "__main__":
    main()
