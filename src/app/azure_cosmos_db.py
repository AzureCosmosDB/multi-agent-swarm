import config
import uuid

from azure.identity import DefaultAzureCredential
from azure.cosmos import CosmosClient, PartitionKey, exceptions

import azure_open_ai

# Initialize the Cosmos client
# reference environment variables for the values of these variables
endpoint = config.AZURE_COSMOSDB_ENDPOINT
credential = DefaultAzureCredential()
client = CosmosClient(endpoint, credential)
print("Authenticated using DefaultAzureCredential")
print("Cosmos client initialized")

# Create global variables for the database and containers
global DATABASE_NAME, USERS_CONTAINER_NAME, PURCHASE_HISTORY_CONTAINER_NAME, PRODUCTS_CONTAINER_NAME, CHAT_CONTAINER_NAME
global DATABASE, USERS_CONTAINER, PURCHASE_HISTORY_CONTAINER, PRODUCTS_CONTAINER, CHAT_CONTAINER

# Database and container names
DATABASE_NAME = "MultiAgentDemoDB"
USERS_CONTAINER_NAME = "Users"
PURCHASE_HISTORY_CONTAINER_NAME = "PurchaseHistory"
PRODUCTS_CONTAINER_NAME = "Products"
CHAT_CONTAINER_NAME = "Chat"

# Database and container references (hydrated in create_database)
DATABASE = None
USERS_CONTAINER = None
PURCHASE_HISTORY_CONTAINER = None
PRODUCTS_CONTAINER = None
CHAT_CONTAINER = None

# Create database and containers if they don't exist
def create_database():
    global DATABASE, USERS_CONTAINER, PURCHASE_HISTORY_CONTAINER, PRODUCTS_CONTAINER, CHAT_CONTAINER
    
    try:
        DATABASE = client.create_database_if_not_exists(id=DATABASE_NAME)
        
        USERS_CONTAINER = DATABASE.create_container_if_not_exists(
            id=USERS_CONTAINER_NAME,
            partition_key=PartitionKey(path="/user_id")
        )
        
        PURCHASE_HISTORY_CONTAINER = DATABASE.create_container_if_not_exists(
            id=PURCHASE_HISTORY_CONTAINER_NAME,
            partition_key=PartitionKey(path="/user_id")
        )
        
        vector_embedding_policy = {
            "vectorEmbeddings": [
                {
                    "path": "/product_description_vector",
                    "dataType": "float32",
                    "distanceFunction": "cosine",
                    "dimensions": 1536
                },
            ]
        }
        diskann_indexing_policy = {
            "includedPaths": [
                {"path": "/*"}
            ],
            "excludedPaths": [
                {"path": "/\"_etag\"/?"}
            ],
            "vectorIndexes": [
                {
                    "path": "/product_description_vector",
                    "type": "diskANN",
                }
            ]
        }
        PRODUCTS_CONTAINER = DATABASE.create_container_if_not_exists(
            id=PRODUCTS_CONTAINER_NAME,
            partition_key=PartitionKey(path="/product_id"),
            vector_embedding_policy=vector_embedding_policy,
            indexing_policy=diskann_indexing_policy
        )
        
        CHAT_CONTAINER = DATABASE.create_container_if_not_exists(
            id=CHAT_CONTAINER_NAME,
            partition_key=PartitionKey(path=["/user_id", "/session_id"], kind="MultiHash"),
            indexing_policy={
                "automatic": True,
                "indexingMode": "consistent"
            }
        )
        
    except exceptions.CosmosHttpResponseError as e:
        print(f"Database creation failed: {e}")

def add_user(user_id, first_name, last_name, email, phone):
    
    
    user = {
        "id": str(user_id),
        "user_id": user_id,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone
    }
    try:
        USERS_CONTAINER.create_item(body=user)
    except exceptions.CosmosResourceExistsError:
        print(f"User with user_id {user_id} already exists.")

def add_purchase(user_id, date_of_purchase, item_id, amount):
    
    purchase = {
        "id": f"{user_id}_{item_id}_{date_of_purchase}",
        "user_id": user_id,
        "date_of_purchase": date_of_purchase,
        "item_id": item_id,
        "amount": amount
    }
    try:
        PURCHASE_HISTORY_CONTAINER.create_item(body=purchase)
    except exceptions.CosmosResourceExistsError:
        print(f"Purchase already exists for user_id {user_id} on {date_of_purchase} for item_id {item_id}.")

def add_product(product_id, product_name, product_description, price):
    
    
    product_description_vector = azure_open_ai.generate_embedding(product_description)
    
    product = {
        "id": str(product_id),
        "product_id": product_id,
        "product_name": product_name,
        "product_description": product_description,
        "product_description_vector": product_description_vector,
        "price": price
    }
    
    try:
        PRODUCTS_CONTAINER.create_item(body=product)
    except exceptions.CosmosResourceExistsError:
        print(f"Product with product_id {product_id} already exists.")

def preview_table(container_name):
    
    container = DATABASE.get_container_client(container_name)
    
    items = container.query_items(
        query="SELECT * FROM c",
        enable_cross_partition_query=True
    )
    
    # Clean up the items for display
    for item in items:
        item.pop("_rid", None)
        item.pop("_self", None)
        item.pop("_etag", None)
        item.pop("_attachments", None)
        item.pop("_ts", None)
        if (container_name == PRODUCTS_CONTAINER_NAME):
            # redact the vectors for the product description
            item.pop("product_description_vector", None)
        print(item)

def get_agent_history(user_id = None, session_id = None):
    
    container = DATABASE.get_container_client(CHAT_CONTAINER_NAME)
    
    items = container.query_items(
        query="SELECT * FROM c WHERE c.user_id=@user_id AND c.session_id=@session_id",
        parameters=[
            {"name": "@user_id", "value": user_id},
            {"name": "@session_id", "value": session_id}
        ],
        enable_cross_partition_query=False
    )
    
    items = container.query_items("SELECT * FROM c",
        enable_cross_partition_query=True
    )
    
    # Convert iterator to list
    items = list(items)
    
    # Clean up the items for display
    for item in items:
        item.pop("id", None)
        item.pop("user_id", None)
        item.pop("session_id", None)
        item.pop("_rid", None)
        item.pop("_self", None)
        item.pop("_etag", None)
        item.pop("_attachments", None)
        item.pop("_ts", None)
        print(item)
        
    return items

def add_agent_message(message):
    
    try:
        CHAT_CONTAINER.create_item(body=message, enable_automatic_id_generation=True)
    except exceptions.CosmosResourceExistsError:
        print("error")
        #print(f"Chat message already exists for user_id {message["userId"]} in session {message["sessionId"]}.")

def tx_batch_add_agent_messages(user_id, session_id, messages):
    
    try:
        batch_operations = []

        for message in messages:
            message["id"] = str(uuid.uuid4()) # Generate a new unique ID for each message
            tuple_to_append = ("create", (message,))
            batch_operations.append(tuple_to_append)

        partition_key = [user_id, session_id]
    
        # Execute the batch operation
        response = CHAT_CONTAINER.execute_item_batch(partition_key=partition_key, batch_operations=batch_operations)
        #print("\nResults for the batch operations: {}\n".format(response))
        
    except exceptions.CosmosHttpResponseError as e:
        print(f"An error occurred: {e.message}")

# Initialize and load database
def initialize_database():
    
    # Create the database and containers if not exists (legacy, rerun azd up if needed)
    create_database()

    # Add some initial users
    initial_users = [
        (1, "Alice", "Smith", "alice@test.com", "123-456-7890"),
        (2, "Bob", "Johnson", "bob@test.com", "234-567-8901"),
        (3, "Sarah", "Brown", "sarah@test.com", "555-567-8901"),
    ]

    for user in initial_users:
        add_user(*user)

    # Add some initial purchases
    initial_purchases = [
        (1, "2024-01-01", 101, 99.99),
        (2, "2023-12-25", 100, 39.99),
        (3, "2023-11-14", 307, 49.99),
    ]

    for purchase in initial_purchases:
        add_purchase(*purchase)

    initial_products = [
        (7, "Hat", "A hat is a stylish and functional accessory designed to shield the "
            "head from the elements while adding a touch of personality to any outfit. "
            "Crafted from materials such as wool, cotton, straw, or synthetic blends, hats come "
            "in a variety of shapes and designs, from wide-brimmed sun hats to snug beanies and classic fedoras. "
            "They offer versatile use, providing protection from sun, rain, or cold while serving as a "
            "fashionable statement piece. Whether for outdoor adventures, formal occasions, "
            "or casual outings, a hat combines practicality and style, making it a "
            "timeless wardrobe essential", 19.99),
        (8, "Wool socks", "Wool socks are premium, cozy footwear accessories designed "
            "to provide exceptional warmth, comfort, and moisture-wicking properties. "
            "Made from natural wool fibers, they are ideal for keeping feet insulated in "
            "cold weather while remaining breathable in warmer conditions. These socks are soft, "
            "durable, and naturally odor-resistant, making them perfect for everyday wear, "
            "outdoor adventures, or lounging at home. With their ability to regulate "
            "temperature and cushion feet, wool socks offer unparalleled comfort, "
            "making them an essential addition to any wardrobe, whether for hiking, working, "
            "or simply relaxing.", 29.99),
        (9, "Shoes","Shoes are versatile footwear designed to protect and comfort "
                "the feet while enabling effortless movement and style. They "
                "come in a wide range of designs, materials, and functions, catering "
                "to various activities, from formal occasions to rugged outdoor adventures. "
                "Crafted from durable materials such as leather, canvas, or synthetic blends, "
                "shoes provide support, cushioning, and stability through features like rubber soles, "
                "padded insoles, and secure fastenings. Available in diverse styles such as sneakers, boots, "
                "sandals, and dress shoes, they blend functionality with aesthetic appeal, making them a staple "
                "for every wardrobe", 39.99),
    ]

    for product in initial_products:
        add_product(*product)