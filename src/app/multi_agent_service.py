import datetime
import random

from swarm import Swarm, Agent
from swarm.repl import run_demo_loop
from swarm.repl.repl import process_and_print_streaming_response, pretty_print_messages

import config
import azure_cosmos_db
import azure_open_ai


# Initialize Swarm client with Azure OpenAI client
swarm_client = Swarm(client=azure_open_ai.aoai_client)


def refund_item(user_id, item_id):
    """Initiate a refund based on the user ID and item ID.
    Takes as input arguments in the format '{"user_id":1,"item_id":3}'
    """
    
    try:
        container = azure_cosmos_db.PURCHASE_HISTORY_CONTAINER
        
        query = "SELECT c.amount FROM c WHERE c.user_id=@user_id AND c.item_id=@item_id"
        parameters = [
            {"name": "@user_id", "value": int(user_id)},
            {"name": "@item_id", "value": int(item_id)}
        ]
        items = list(container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        
        if items:
            amount = items[0]['amount']
            # Refund the amount to the user
            refund_message = f"Refunding ${amount} to user ID {user_id} for item ID {item_id}."
            return refund_message
        else:
            refund_message = f"No purchase found for user ID {user_id} and item ID {item_id}. Refund initiated."
            return refund_message
    
    except Exception as e:
        print(f"An error occurred during refund: {e}")


def notify_customer(user_id, method):
    """Notify a customer by their preferred method of either phone or email.
    Takes as input arguments in the format '{"user_id":1,"method":"email"}'"""
    
    try:
        container = azure_cosmos_db.USERS_CONTAINER
        
        query = "SELECT c.email, c.phone FROM c WHERE c.user_id=@user_id"
        parameters = [{"name": "@user_id", "value": int(user_id)}]
        items = list(container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        
        if items:
            email, phone = items[0]['email'], items[0]['phone']
            if method == "email" and email:
                print(f"Emailed customer {email} a notification.")
            elif method == "phone" and phone:
                print(f"Texted customer {phone} a notification.")
            else:
                print(f"No {method} contact available for user ID {user_id}.")
        else:
            print(f"User ID {user_id} not found.")
    
    except Exception as e:
        print(f"An error occurred during notification: {e}")


def order_item(user_id, product_id):
    """Place an order for a product based on the user ID and product ID.
    Takes as input arguments in the format '{"user_id":1,"product_id":2}'"""
    
    try:
        # Get the current date and time for the purchase
        date_of_purchase = datetime.datetime.now().isoformat()
        # Generate a random item ID
        item_id = random.randint(1, 300)


        container = azure_cosmos_db.PRODUCTS_CONTAINER
        
        # Query the database for the product information
        query = "SELECT c.product_id, c.product_name, c.price FROM c WHERE c.product_id=@product_id"
        parameters = [{"name": "@product_id", "value": int(product_id)}]
        items = list(container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        
        if items:
            product = items[0]
            product_id, product_name, price = product['product_id'], product['product_name'], product['price']
            
            print(f"Ordering product {product_name} for user ID {user_id}. The price is {price}.")
            
            # Add the purchase to the database
            azure_cosmos_db.add_purchase(int(user_id), date_of_purchase, item_id, price)
            
            order_item_message = f"Order placed for product {product_name} for user ID {user_id}. Item ID: {item_id}."
            return order_item_message
        else:
            order_item_message = f"Product {product_id} not found."
            return order_item_message
    
    except Exception as e:
        print(f"An error occurred during order placement: {e}")


def product_information(user_prompt):
    """Provide information about a product based on the user prompt.
    Takes as input the user prompt as a string."""
    
    # Perform a vector search on the Cosmos DB container and return results to the agent
    vectors = azure_open_ai.generate_embedding(user_prompt)
    vector_search_results = product_vector_search(vectors)
    
    return vector_search_results


# Perform a vector search on the Cosmos DB container
def product_vector_search(vectors, similarity_score=0.02, num_results=3):
    
    # Execute the query
    container = azure_cosmos_db.PRODUCTS_CONTAINER
    
    results = container.query_items(
        query='''
        SELECT TOP @num_results c.product_id, c.price, c.product_description, VectorDistance(c.product_description_vector, @embedding) as SimilarityScore 
        FROM c
        WHERE VectorDistance(c.product_description_vector,@embedding) > @similarity_score
        ORDER BY VectorDistance(c.product_description_vector,@embedding)
        ''',
        parameters=[
            {"name": "@embedding", "value": vectors},
            {"name": "@num_results", "value": num_results},
            {"name": "@similarity_score", "value": similarity_score}
        ],
        enable_cross_partition_query=True, populate_query_metrics=True)
    
    print("Executed vector search in Azure Cosmos DB... \n")
    results = list(results)
    
    # Extract the necessary information from the results
    formatted_results = []
    
    for result in results:
        score = result.pop('SimilarityScore')
        result['product_id'] = str(result['product_id'])
        result['product_description'] = "product id " + result['product_id'] + ": " + result['product_description']
        # add price to product_description as well
        result['product_description'] += " price: " + str(result['price'])

        formatted_result = {
            'SimilarityScore': score,
            'document': result
        }
        formatted_results.append(formatted_result)
        
    return formatted_results


# Initialize the database
azure_cosmos_db.initialize_database()

# Preview tables
azure_cosmos_db.preview_table("Users")
azure_cosmos_db.preview_table("PurchaseHistory")
azure_cosmos_db.preview_table("Products")


# define the transfer functions for each agent
def transfer_to_sales():
    return sales_agent

def transfer_to_refunds():
    return refunds_agent

def transfer_to_product():
    return product_agent

def transfer_to_triage():
    return triage_agent


# Define the agents
refunds_agent = Agent(
    name="Refunds Agent",
    functions=[transfer_to_triage, refund_item, notify_customer],
    model=config.AZURE_OPENAI_GPT_DEPLOYMENT,
    instructions="""You are a refund agent that handles all actions related to refunds after a return has been processed.
    You must ask for both the user ID and item ID to initiate a refund. 
    If item_id is present in the context information, use it. 
    Otherwise, do not make any assumptions, you must ask for the item ID as well.
    Ask for both user_id and item_id in one message.
    Do not use any other context information to determine whether the right user id or item id has been provided - just accept the input as is.
    If the user asks you to notify them, you must ask them what their preferred method of notification is. For notifications, you must
    ask them for user_id and method in one message.
    If the user asks you a question you cannot answer, transfer back to the triage agent."""
)

sales_agent = Agent(
    name="Sales Agent",
    model=config.AZURE_OPENAI_GPT_DEPLOYMENT,
    functions=[transfer_to_triage, order_item, notify_customer, transfer_to_refunds],
    instructions="""You are a sales agent that handles all actions related to placing an order to purchase an item.
    Regardless of what the user wants to purchase, must ask for the user ID. 
    If the product id is present in the context information, use it. Otherwise, you must as for the product ID as well.
    An order cannot be placed without these two pieces of information. Ask for both user_id and product_id in one message.
    If the user asks you to notify them, you must ask them what their preferred method is. For notifications, you must
    ask them for user_id and method in one message.
    If the user asks you a question you cannot answer, transfer back to the triage agent."""
)

product_agent = Agent(
    name="Product Agent",
    model=config.AZURE_OPENAI_GPT_DEPLOYMENT,
    functions=[transfer_to_triage, product_information, transfer_to_sales, transfer_to_refunds],
    add_backlinks=True,
    instructions="""You are a product agent that provides information about products in the database.
    When calling the product_information function, do not make any assumptions 
    about the product id, or number the products in the response. Instead, use the product id from the response to 
    product_information and align that product id whenever referring to the corresponding product in the database. 
    Only give the user very basic information about the product; the product name, id, and very short description.
    If the user asks for more information about any product, provide it. 
    If the user asks you a question you cannot answer, transfer back to the triage agent.
    """
)

triage_agent = Agent(
    name="Triage Agent",
    agents=[sales_agent, refunds_agent, product_agent],
    functions=[transfer_to_sales, transfer_to_refunds, transfer_to_product],
    model=config.AZURE_OPENAI_GPT_DEPLOYMENT,
    add_backlinks=True,
    instructions="""You are to triage a users request, and call a tool to transfer to the right intent.
    Otherwise, once you are ready to transfer to the right intent, call the tool to transfer to the right intent.
    You dont need to know specifics, just the topic of the request.
    If the user asks for product information, transfer to the Product Agent.
    If the user request is about making an order or purchasing an item, transfer to the Sales Agent.
    If the user request is about getting a refund on an item or returning a product, transfer to the Refunds Agent.
    If the user requests something else, say you are not trained to handle that request.
    When you need more information to triage the request to an agent, ask a direct question without explaining why you're asking it.
    Do not share your thought process with the user! Do not make unreasonable assumptions on behalf of user."""
)

for f in triage_agent.functions:
    print(f.__name__)

triage_agent.functions = [transfer_to_sales, transfer_to_refunds, transfer_to_product]

def run_demo_loop(starting_agent, context_variables=None, stream=False, debug=False) -> None:
    
    client = swarm_client
    print("Starting Swarm CLI 🐝")

    messages = []
    agent = starting_agent

    while True:
        
        # Format the displayed "User:" text in grey to offset from user input
        user_input = input("\033[90mUser\033[0m: ")
        messages.append({"role": "user", "content": user_input})

        response = client.run(
            agent=agent,
            messages=messages,
            context_variables=context_variables or {},
            stream=stream,
            debug=debug,
        )

        if stream:
            response = process_and_print_streaming_response(response)
        else:
            pretty_print_messages(response.messages)

        messages.extend(response.messages)
        
        agent = response.agent

if __name__ == "__main__":
    # Run the demo loop
    run_demo_loop(triage_agent, debug=True)

