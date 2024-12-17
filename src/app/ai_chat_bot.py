import gradio as gr
from swarm import Swarm, Agent
from multi_agent_service import triage_agent, sales_agent, refunds_agent, product_agent  # Import all agents
import azure_open_ai

# Initialize Swarm client
client = Swarm(client=azure_open_ai.aoai_client)

# Map agent names to agent objects
agent_map = {
    "Triage Agent": triage_agent,
    "Sales Agent": sales_agent,
    "Refunds Agent": refunds_agent,
    "Product Agent": product_agent,
}


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

    # Filter and format responses to ensure valid content
    assistant_responses = [
        {"role": "assistant", "content": message["content"]}
        for message in response.messages
        if message["role"] == "assistant" and message.get("content")  # Ensure 'content' exists and is not None
    ]
    messages.extend(response.messages)

    # Combine user and assistant messages for Chatbot display
    chatbot_messages = [
        {"role": msg["role"], "content": msg["content"] or "[No content]"}  # Fallback for empty content
        for msg in messages if msg.get("content") is not None
    ]

    # Update agent state
    next_agent = response.agent.name

    return chatbot_messages, next_agent, messages


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
            elem_id="user_input",
        )

    agent_name = gr.State("Triage Agent")
    messages = gr.State([])

    # Chat interaction
    user_input.submit(
        fn=chat_interface,
        inputs=[user_input, agent_name, messages],
        outputs=[chatbot, agent_name, messages],
    ).then(
        lambda: "", inputs=None, outputs=user_input
    )  # Clear the input box after submission

demo.launch()