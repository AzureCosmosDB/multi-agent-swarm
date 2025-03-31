import gradio as gr
from swarm import Swarm, Agent

# Import all agents
from multi_agent_service import triage_agent, sales_agent, refunds_agent, product_agent
import azure_open_ai
from azure_cosmos_db import add_agent_message, get_agent_history, tx_batch_add_agent_messages


# Initialize Swarm client
client = Swarm(client=azure_open_ai.aoai_client)

# Map agent names to agent objects
agent_map = {
    "Triage Agent": triage_agent,
    "Sales Agent": sales_agent,
    "Refunds Agent": refunds_agent,
    "Product Agent": product_agent,
}

# Fetch agent history from Cosmos DB
#messages = get_agent_history("mark", "1234")

# Input from user comes here, put breakpoint here to debug the agent workflow
def chat_interface(user_input, agent_name="Triage Agent", messages=None):
    
    if messages is None:
        messages = []


    # Update messages with user input
    messages.append({"role": "user", "content": user_input})

    # Get the current agent object from the map
    agent = agent_map.get(agent_name, triage_agent)

    # Call the Swarm API
    response = client.run(
        agent=agent,
        messages=messages,
        context_variables={},
        stream=False,  # Set True for streaming support
        debug=False,
    )
    
    user_id = "mark"
    session_id = "1234"
    
    # Persist the user input and Agent responses to Cosmos DB in a Transaction
    # Create a new message object for the user input to save in Cosmos DB
    cosmos_message = []
    cosmos_message.append({"role": "user", "content": user_input, "userId": user_id, "sessionId": session_id})
    
    for m in response.messages:
        m["userId"] = user_id
        m["sessionId"] = session_id
        cosmos_message.append(m)
    
    tx_batch_add_agent_messages(user_id=user_id, session_id=session_id, messages=cosmos_message)
    
    
    # Prepare chatbot messages for display
    # Gradle expects a list of dictionaries with "role" and "content"
    # Initialize chatbot messages list
    messages.extend(response.messages)
    
    chatbot_messages = format_for_gradio(messages)
    
    #chatbot_messages = []

    # for i, msg in enumerate(messages):
    #     if msg["role"] == "user":
    #         message = msg.get("content") or ""
    #         # Append user messages directly
    #         chatbot_messages.append({"role": "user", "content": f"<span style='color:blue'>{message}</span>\n\n"})

    #     elif msg["role"] == "tool":
    #         # Capture debug info from tool messages
    #         tool_name = msg.get("tool_name") or ""
    #         tool_content = msg.get("content") or ""
    #         message = f"[Debug Info: Tool: {tool_name}, Content: {tool_content}]"
    #         # Append tool messages with debug info
    #         chatbot_messages.append({"role": "assistant", "content": f"<span style='color:red'>{message}</span>\n\n"})

    #     elif msg["role"] == "assistant":
    #         # Capture sender from assistant messages
    #         responding_agent = msg.get("sender") or ""
    #         agent_response = msg.get("content") or "Preparing Transfer..."

    #         # Include sender in the assistant message content
    #         message = f"[{responding_agent}] {agent_response}\n\n"
    #         # Append assistant messages with the agent who sent
    #         chatbot_messages.append({"role": "assistant", "content": message})

    # Update agent state
    next_agent = response.agent.name

    return chatbot_messages, next_agent, messages


def format_for_gradio(messages):
    """Format messages for Gradio Chatbot component."""
    
    chatbot_messages = []

    for i, msg in enumerate(messages):
        if msg["role"] == "user":
            message = msg.get("content") or ""
            # Append user messages directly
            chatbot_messages.append({"role": "user", "content": f"<span style='color:blue'>{message}</span>\n\n"})

        elif msg["role"] == "tool":
            # Capture debug info from tool messages
            tool_name = msg.get("tool_name") or ""
            tool_content = msg.get("content") or ""
            message = f"[Debug Info: Tool: {tool_name}, Content: {tool_content}]"
            # Append tool messages with debug info
            chatbot_messages.append({"role": "assistant", "content": f"<span style='color:red'>{message}</span>\n\n"})

        elif msg["role"] == "assistant":
            # Capture sender from assistant messages
            responding_agent = msg.get("sender") or ""
            agent_response = msg.get("content") or "Preparing Transfer..."

            # Include sender in the assistant message content
            message = f"[{responding_agent}] {agent_response}\n\n"
            # Append assistant messages with the agent who sent
            chatbot_messages.append({"role": "assistant", "content": message})

    return chatbot_messages


# Define Gradio UI
with gr.Blocks(css=".chatbox { background-color: #f9f9f9; border-radius: 10px; padding: 10px; }") as demo:
    
    gr.Markdown(
        """
        # Personal Shopping AI Assistant
        Welcome to your Personal Shopping AI Assistant. 
        Get help with shopping, refunds, product information, and more!
        """,
        elem_id="header",
    )

    with gr.Row():
        chatbot = gr.Chatbot(
            label="Chat with the Assistant",
            elem_classes=["chatbox"],
            type="messages"
        )

    with gr.Row():
        user_input = gr.Textbox(
            placeholder="Enter your message here...",
            label="Your Message",
            lines=1,
            elem_id="user_input"
        )

    agent_name = gr.State("Triage Agent")
    messages = gr.State([])
    
    # Fetch agent history from Cosmos DB
    chatbot_messages = get_agent_history("mark", "1234")
    chatbot_messages = format_for_gradio(chatbot_messages)
    # doesn't work.
    #messages=chatbot_messages
    

    # Chat interaction
    user_input.submit(
        fn=chat_interface,
        inputs=[user_input, agent_name, messages],
        outputs=[chatbot, agent_name, messages],
    ).then(
        lambda: "", inputs=None, outputs=user_input
    )  # Clear the input box after submission

demo.launch()