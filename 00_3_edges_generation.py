import requests
from urllib.parse import urljoin

from mongodbDriver import MongoDBManager

import signal

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Request took too long")

signal.signal(signal.SIGALRM, timeout_handler)


def process_instance(instance_name):
    result = {"peers": None, "domain_blocks": None, "errors": []}

    # URLs to fetch data from
    domain_blocks_url = urljoin(
        f"https://{instance_name}", "/api/v1/instance/domain_blocks"
    )
    peers_url = urljoin(f"https://{instance_name}", "/api/v1/instance/peers")

    # Fetch the peers
    try:
        signal.alarm(10)  # Set a 10-second hard timeout
        peers_response = requests.get(peers_url, timeout=(5, 10))
        signal.alarm(0)  # Cancel the alarm after the request completes
        peers_response.raise_for_status()  # Raise an exception for HTTP errors
        peers_data = peers_response.json()
        if (
            not peers_response.headers.get("Content-Type", "").startswith(
                "application/json"
            )
            or "error" in peers_data
        ):
            raise ValueError(
                f"Error from peers endpoint: {peers_data['error_description']}"
            )
        result["peers"] = peers_data
    except TimeoutException:
        result["errors"].append({"peers": "Request exceeded hard timeout limit"})
    except requests.exceptions.RequestException as e:
        result["errors"].append({"peers": f"Request error: {str(e)}"})
    except ValueError as e:
        result["errors"].append({"peers": f"Value error: {str(e)}"})

    # Fetch the domain blocks
    try:
        signal.alarm(10)  # Set a 10-second hard timeout
        domain_blocks_response = requests.get(domain_blocks_url, timeout=(5, 10))
        signal.alarm(0)  # Cancel the alarm after the request completes
        domain_blocks_response.raise_for_status()  # Raise an exception for HTTP errors
        domain_blocks_data = domain_blocks_response.json()
        if (
            not domain_blocks_response.headers.get("Content-Type", "").startswith(
                "application/json"
            )
            or "error" in domain_blocks_data
        ):
            raise ValueError(
                f"Error from domain blocks endpoint: {domain_blocks_data['error_description']}"
            )
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

        # Fetch all document names (to create the global set for intersection)
        all_names = set(collection.distinct("name", {"instance_type": "MASTODON"}))

        documents = collection.find(
            {"edge_col_status": "NOT_STARTED"}, {"name": 1}
        )

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
                # Process the instance to get peers, domain_blocks, and errors
                result = process_instance(instance_name)

                # Determine the appropriate status based on errors
                if any("peers" in error for error in result["errors"]):
                    status = "peers_unreachable"
                elif any("blocks" in error for error in result["errors"]):
                    status = "blocklist_unreachable"
                else:
                    status = "SUCCESS"

                # Calculate valid_neighbors
                peers = set(result["peers"] or [])
                domain_blocks = set(
                    [
                        block["domain"] for block in (result["domain_blocks"] or [])
                    ]  # Extract domain from full block data
                )
                # domain_blocks = set(result["domain_blocks"] or [])
                valid_neighbors = list((peers - domain_blocks) & all_names)

                # Update the document with results and status
                collection.update_one(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            # "neighbors": result["peers"] or [],
                            # "blocked_neighbors": result["domain_blocks"] or [],
                            "valid_neighbors": valid_neighbors,
                            "errors": result["errors"],
                            "edge_col_status": status,
                        }
                    },
                )
                print(f"{status} : Instance {instance_name} ")

            except Exception as e:
                # Handle critical errors and set edge_col_status to ERROR
                collection.update_one(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "edge_col_status": "ERROR",
                            "errors": [f"Critical failure: {str(e)}"],
                        }
                    },
                )
                print(f"Failed to process instance {instance_name}: {str(e)}")

    finally:
        # Close the connection
        db_manager.close()


if __name__ == "__main__":
    main()
