import os
import azure_open_ai

from azure.cosmos import CosmosClient, PartitionKey, exceptions

# Initialize the Cosmos client
# reference environment variables for the values of these variables
endpoint = os.environ['AZURE_COSMOSDB_ENDPOINT']
key = os.environ['AZURE_COSMOSDB_KEY']
client = CosmosClient(endpoint, key)

# Database and container names
database_name = "MultiAgentDemoDB"
users_container_name = "Users"
purchase_history_container_name = "PurchaseHistory"
products_container_name = "Products"

# Create database and containers if they don't exist
def create_database():
    try:
        database = client.create_database_if_not_exists(id=database_name)
        users_container = database.create_container_if_not_exists(
            id=users_container_name,
            partition_key=PartitionKey(path="/user_id"),
            offer_throughput=400
        )
        purchase_history_container = database.create_container_if_not_exists(
            id=purchase_history_container_name,
            partition_key=PartitionKey(path="/user_id"),
            offer_throughput=400
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
        products_container = database.create_container_if_not_exists(
            id=products_container_name,
            partition_key=PartitionKey(path="/product_id"),
            offer_throughput=400,
            vector_embedding_policy=vector_embedding_policy,
            indexing_policy=diskann_indexing_policy
        )
    except exceptions.CosmosHttpResponseError as e:
        print(f"Database creation failed: {e}")

def add_user(user_id, first_name, last_name, email, phone):
    database = client.get_database_client(database_name)
    container = database.get_container_client(users_container_name)
    user = {
        "id": str(user_id),
        "user_id": user_id,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone
    }
    try:
        container.create_item(body=user)
        rangeIds = container.client_connection._ReadPartitionKeyRanges()
        container.query_items_change_feed(partition_key_range_id="0")
    except exceptions.CosmosResourceExistsError:
        print(f"User with user_id {user_id} already exists.")

def add_purchase(user_id, date_of_purchase, item_id, amount):
    database = client.get_database_client(database_name)
    container = database.get_container_client(purchase_history_container_name)
    purchase = {
        "id": f"{user_id}_{item_id}_{date_of_purchase}",
        "user_id": user_id,
        "date_of_purchase": date_of_purchase,
        "item_id": item_id,
        "amount": amount
    }
    try:
        container.create_item(body=purchase)
    except exceptions.CosmosResourceExistsError:
        print(f"Purchase already exists for user_id {user_id} on {date_of_purchase} for item_id {item_id}.")

def add_product(product_id, product_name, product_description, price):
    database = client.get_database_client(database_name)
    container = database.get_container_client(products_container_name)
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
        container.create_item(body=product)
    except exceptions.CosmosResourceExistsError:
        print(f"Product with product_id {product_id} already exists.")

def preview_table(container_name):
    database = client.get_database_client(database_name)
    container = database.get_container_client(container_name)
    items = container.query_items(
        query="SELECT * FROM c",
        enable_cross_partition_query=True
    )
    for item in items:
        if (container_name == products_container_name):
            # redact the product description vector
            item.pop("product_description_vector", None)
        print(item)

# Initialize and load database
def initialize_database():
    create_database()

    # Add some initial users
    initial_users = [
        (1, "Alice", "Smith", "alice@test.com", "123-456-7890"),
        (2, "Bob", "Johnson", "bob@test.com", "234-567-8901"),
        (3, "Sarah", "Brown", "sarah@test.com", "555-567-8901"),
        # Add more initial users here
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
                          "or simply relaxing.",29.99),
        (9, "Shoes","Shoes are versatile footwear designed to protect and comfort "
                    "the feet while enabling effortless movement and style. They "
                    "come in a wide range of designs, materials, and functions, catering "
                    "to various activities, from formal occasions to rugged outdoor adventures. "
                    "Crafted from durable materials such as leather, canvas, or synthetic blends, "
                    "shoes provide support, cushioning, and stability through features like rubber soles, "
                    "padded insoles, and secure fastenings. Available in diverse styles such as sneakers, boots, "
                    "sandals, and dress shoes, they blend functionality with aesthetic appeal, making them a staple "
                    "for every wardrobe",39.99),
    ]

    for product in initial_products:
        add_product(*product)