import requests
from urllib.parse import urljoin
from mongodbDriver import MongoDBManager
import signal

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Request took too long")

signal.signal(signal.SIGALRM, timeout_handler)


def is_mastodon_instance(instance_name):
    """Check if an instance is Mastodon by calling /api/v2/instance."""
    url = urljoin(f"https://{instance_name}", "/api/v2/instance")
    try:
        signal.alarm(10)
        resp = requests.get(url, timeout=(5, 10))
        signal.alarm(0)

        resp.raise_for_status()

        data = resp.json()
        api_versions = data.get("api_versions")
        source_url = data.get("source_url", "")

        # Primary check: api_versions
        if isinstance(api_versions, dict) and "mastodon" in api_versions:
            return True

        # Fallback: source_url
        if isinstance(source_url, str) and "mastodon" in source_url.lower():
            return True

        return False

    except (TimeoutException, requests.exceptions.RequestException, ValueError):
        return False
    except Exception:
        return False


def process_instance(instance_name):
    result = {"peers": None, "domain_blocks": None, "errors": []}

    # URLs to fetch data from
    domain_blocks_url = urljoin(f"https://{instance_name}", "/api/v1/instance/domain_blocks")
    peers_url = urljoin(f"https://{instance_name}", "/api/v1/instance/peers")

    # Fetch the peers
    try:
        signal.alarm(10)
        peers_response = requests.get(peers_url, timeout=(5, 10))
        signal.alarm(0)
        peers_response.raise_for_status()
        peers_data = peers_response.json()
        if not peers_response.headers.get("Content-Type", "").startswith("application/json") or "error" in peers_data:
            raise ValueError(f"Error from peers endpoint: {peers_data.get('error_description')}")
        result["peers"] = peers_data
    except TimeoutException:
        result["errors"].append({"peers": "Request exceeded hard timeout limit"})
    except requests.exceptions.RequestException as e:
        result["errors"].append({"peers": f"Request error: {str(e)}"})
    except ValueError as e:
        result["errors"].append({"peers": f"Value error: {str(e)}"})

    # Fetch the domain blocks
    try:
        signal.alarm(10)
        domain_blocks_response = requests.get(domain_blocks_url, timeout=(5, 10))
        signal.alarm(0)
        domain_blocks_response.raise_for_status()
        domain_blocks_data = domain_blocks_response.json()
        if not domain_blocks_response.headers.get("Content-Type", "").startswith("application/json") or "error" in domain_blocks_data:
            raise ValueError(f"Error from domain blocks endpoint: {domain_blocks_data.get('error_description')}")
        result["domain_blocks"] = domain_blocks_data
    except TimeoutException:
        result["errors"].append({"blocks": "Request exceeded hard timeout limit"})
    except requests.exceptions.RequestException as e:
        result["errors"].append({"blocks": f"Request error: {str(e)}"})
    except ValueError as e:
        result["errors"].append({"blocks": f"Value error: {str(e)}"})

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

        # If DB is empty, insert 5 seeds
        if collection.count_documents({}) == 0:
            seeds = ["mastodon.social", "fosstodon.org", "mstdn.social", "pawoo.net", "mastodon.online"]
            for seed in seeds:
                collection.insert_one({"name": seed, "instance_type": "NAN"})
            print(f"Inserted {len(seeds)} seeds.")

        while True:
            # Fetch unprocessed instances
            unprocessed = list(collection.find({"instance_type": "NAN"}, {"name": 1}).limit(1000))
            if not unprocessed:
                print("Crawling process finished")
                break

            print(f"Starting round with {len(unprocessed)} instances.\n")

            for doc in unprocessed:
                instance_name = doc.get("name")
                if not instance_name:
                    continue

                instance_type = "NAN"
        
                try:
                    # Step 1: Check if Mastodon
                    if not is_mastodon_instance(instance_name):
                        instance_type = "NOT_MASTODON"
                    else:
                        instance_type = "MASTODON"
                
                    # Step 2: Process Mastodon instance
                    result = process_instance(instance_name)

                    peers = set(result["peers"] or [])
                    domain_blocks = set([block["domain"] for block in (result["domain_blocks"] or [])])

                    # Update DB with results
                    collection.update_one({"_id": doc["_id"]}, {"$set": {"instance_type": instance_type}})

                    # Add new peers and blocked instances into DB if not already there
                    new_candidates = list(peers.union(domain_blocks))
                    if new_candidates:
                        # Get existing names in one query
                        existing = set(
                            collection.distinct("name", {"name": {"$in": new_candidates}})
                        )
                        to_insert = [{"name": n, "instance_type": "NAN"} for n in new_candidates if n not in existing]

                        if to_insert:
                            collection.insert_many(to_insert)

                except Exception as e:
                    collection.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {"instance_type": "ERROR", "errors": [f"Critical failure: {str(e)}"]}},
                    )
                    print(f"Failed to process {instance_name}: {str(e)}")

    finally:
        db_manager.close()


if __name__ == "__main__":
    main()
