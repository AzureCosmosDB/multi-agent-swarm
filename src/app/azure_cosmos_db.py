import json
import os
import sys
import uuid
from typing import List, Optional

import azure_open_ai
from azure.cosmos import ContainerProxy, CosmosClient, PartitionKey, exceptions

# Initialize CosmosDB Client

COSMOS_DB_URL = os.getenv("COSMOS_DB_URL")
COSMOS_DB_KEY = os.getenv("COSMOS_DB_KEY")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
DATABASE_NAME = "ProductAssistant"
PRODUCTS_CONTAINER = "Products"
USERS_CONTAINER = "Users"
PURCHASE_HISTORY_CONTAINER = "PurchaseHistory"

client = CosmosClient(COSMOS_DB_URL, COSMOS_DB_KEY)
client.create_database_if_not_exists(DATABASE_NAME)
database = client.get_database_client(DATABASE_NAME)


# Create Containers with Vector and Full-Text Indexing Policies
def create_containers():
    try:
        users_container = database.create_container_if_not_exists(
            id=USERS_CONTAINER,
            partition_key=PartitionKey(path="/user_id"),
            offer_throughput=400,
        )

        print(
            f"Container {USERS_CONTAINER} created."
        )

        purchase_history_container = database.create_container_if_not_exists(
            id=PURCHASE_HISTORY_CONTAINER,
            partition_key=PartitionKey(path="/user_id"),
            offer_throughput=400
        )

        print(
            f"Container {PURCHASE_HISTORY_CONTAINER} created."
        )

        vector_embedding_policy = {
            "vectorEmbeddings": [
                {
                    "path": "/embedding",
                    "dataType": "float32",
                    "dimensions": 1536,
                    "distanceFunction": "cosine",
                }
            ]
        }

        full_text_policy = {
            "defaultLanguage": "en-US",
            "fullTextPaths": [
                {
                    "path": "/product_description",
                    "language": "en-US",
                }
            ]
        }

        indexing_policy = {
                "indexingMode": "consistent",
                "includedPaths": [{"path": "/*"}],
                "excludedPaths": [{"path": '/"_etag"/?'}],
                "vectorIndexes": [{"path": "/embedding", "type": "diskANN"}],
                "fullTextIndexes": [{"path": "/product_description"}],
            }

        products_container = database.create_container_if_not_exists(
            id=PRODUCTS_CONTAINER,
            partition_key=PartitionKey(path="/category"),
            offer_throughput=400,
            vector_embedding_policy=vector_embedding_policy,
            full_text_policy=full_text_policy,
            indexing_policy=indexing_policy,
        )

        print(
            f"Container {PRODUCTS_CONTAINER} created with vector and full-text search indexing."
        )
    except exceptions.CosmosHttpResponseError as e:
        print(f"Container creation failed: {e}")


def add_user(user_id, first_name, last_name, email, phone):
    container = database.get_container_client(USERS_CONTAINER)
    user = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone
    }
    try:
        container.create_item(body=user)
    except exceptions.CosmosResourceExistsError:
        print(f"User with user_id {user_id} already exists.")


def add_purchase(user_id, date_of_purchase, item_id, amount, product_name, category):
    container = database.get_container_client(PURCHASE_HISTORY_CONTAINER)
    purchase = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "date_of_purchase": date_of_purchase,
        "product_id": item_id,
        "product_name": product_name,
        "category": category,
        "amount": amount
    }
    try:
        container.create_item(body=purchase)
    except exceptions.CosmosResourceExistsError:
        print(f"Purchase already exists for user_id {user_id} on {date_of_purchase} for item_id {item_id}.")


def add_product(product_id, product_name, category, product_description, price):
    container = database.get_container_client(PRODUCTS_CONTAINER)
    product_description_vector = azure_open_ai.generate_embedding(product_description)
    product = {
        "id": str(uuid.uuid4()),
        "product_id": product_id,
        "product_name": product_name,
        "category": category,
        "product_description": product_description,
        "product_description_vector": product_description_vector,
        "price": price
    }
    try:
        container.create_item(body=product)
    except exceptions.CosmosResourceExistsError:
        print(f"Product with product_id {product_id} already exists.")


def process_and_insert_data(
        filename: str,
        container: ContainerProxy,
        vector_field: Optional[str] = None,
        full_text_fields: Optional[List[str]] = None,
):
    if not os.path.exists(filename):
        print(f"File {filename} not found.")
        return

    with open(filename, "r") as f:
        data = json.load(f)

    if len(data) > 300:
        data = data[226:]

    for entry in data:
        if full_text_fields is not None:
            for field in full_text_fields:
                if field in entry and isinstance(entry[field], list):
                    entry[field] = [", ".join(map(str, entry[field]))]

        # Generate vector embedding
        if vector_field and vector_field in entry and isinstance(entry[vector_field], str):
            entry["embedding"] = azure_open_ai.generate_embedding(entry[vector_field])

        # Insert into CosmosDB
        entry["id"] = str(uuid.uuid4())
        size = sys.getsizeof(json.dumps(entry))
        if size > 2 * 1024 * 1024:  # 2MB in bytes
            print(f"Document {entry['id']} is too large: {size} bytes")
        container.upsert_item(entry)

    print(f"Inserted data from {filename} into {container.id}.")


def main():
    # Create Containers
    create_containers()

    products_container = database.get_container_client(PRODUCTS_CONTAINER)
    users_container = database.get_container_client(USERS_CONTAINER)
    purchase_history_container = database.get_container_client(PURCHASE_HISTORY_CONTAINER)

    # Insert data into CosmosDB with embedding and indexing
    file_prefix = "/Users/aayushkataria/git/multi-agent-swarm/src/data/"
    process_and_insert_data(
        file_prefix + "final_products.json",
        products_container,
        "product_description",
        ["product_description"],
    )
    process_and_insert_data(file_prefix + "users.json", users_container)
    process_and_insert_data(
        file_prefix + "purchase_history.json",
        purchase_history_container)

    print(
        "Data successfully inserted into CosmosDB with embeddings, vector search, and full-text search indexing!"
    )


if __name__ == "__main__":
    main()
