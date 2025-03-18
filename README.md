# Multi-agent AI sample with Azure Cosmos DB

A sample personal shopping AI Chatbot that can help with product enquiries, making sales, and refunding orders by transferring to different agents for those tasks.

Features:
- **Multi-agent**: [OpenAI Swarm](https://github.com/openai/swarm) to orchestrate multi-agent interactions with [Azure OpenAI](https://learn.microsoft.com/azure/ai-services/openai/overview) API calls.
- **Transactional data management**: planet scale [Azure Cosmos DB database service](https://learn.microsoft.com/azure/cosmos-db/introduction) to store transactional user and product operational data.
- **Retrieval Augmented Generation (RAG)**: [vector search](https://learn.microsoft.com/azure/cosmos-db/nosql/vector-search) in Azure Cosmos DB with powerful [DiskANN index](https://www.microsoft.com/en-us/research/publication/diskann-fast-accurate-billion-point-nearest-neighbor-search-on-a-single-node/?msockid=091c323873cd6bd6392120ac72e46a98) to serve product enquiries from the same database.
- **Gradio UI**: [Gradio](https://www.gradio.app/) to provide a simple UI ChatBot for the end-user.

## Backend agent activity

Run the CLI interactive session to see the agent handoffs in action...

![Demo](./media/demo-cli.gif)

## Front-end AI chat bot

Run the AI chat bot for the end-user experience...

![Demo](./media/demo-chatbot.gif)

## Overview

The personal shopper example includes four main agents to handle various customer service requests:

1. **Triage Agent**: Determines the type of request and transfers to the appropriate agent.
2. **Product Agent**: Answers customer queries from the products container using [Retrieval Augmented Generation (RAG)](https://learn.microsoft.com/azure/cosmos-db/gen-ai/rag).
3. **Refund Agent**: Manages customer refunds, requiring both user ID and item ID to initiate a refund.
4. **Sales Agent**: Handles actions related to placing orders, requiring both user ID and product ID to complete a purchase.

## Prerequisites

- [Azure Cosmos DB account](https://learn.microsoft.com/azure/cosmos-db/) - configured for Serverless and [vector search](https://learn.microsoft.com/azure/cosmos-db/nosql/vector-search).
- [Azure OpenAI Account](https://learn.microsoft.com/azure/ai-services/openai/overview) endpoint with embedding `text-3-embedding-large` and GPT `gpt-4o-mini` models deployed.
- [Azure Developer CLI - AZD](https://learn.microsoft.com/azure/developer/azure-developer-cli/overview) to deploy Azure Services and configure environment variables.

## How to run locally

Clone the repository:

```shell
git clone https://github.com/AzureCosmosDB/multi-agent-swarm
cd multi-agent-swarm
```

Create and activate a virtual environment (Linux/Mac):

```shell
python -m venv venv
source venv/bin/activate
```

```shell
# Install AZD
curl -fsSL https://aka.ms/install-azd.sh | bash
```

Create and activate a virtual environment (Windows):

```shell
python -m venv venv
venv\Scripts\activate
```

```shell
# Install AZD
powershell -ex AllSigned -c "Invoke-RestMethod 'https://aka.ms/install-azd.ps1' | Invoke-Expression"
```


Install dependencies:

```shell
pip install -r requirements.txt
```



Deploy the Azure Services via AZD and inject the service names into the .env file
```shell
azd up
```



From your terminal or IDE, run below and click on URL provided in output:

```shell
python src/app/ai_chat_bot.py
```

To see the agent handoffs, you can also run as an interactive Swarm CLI session using:

```shell
python src/app/multi_agent_service.py
```
