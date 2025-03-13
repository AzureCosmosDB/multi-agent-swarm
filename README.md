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

- [Azure Cosmos DB account](https://learn.microsoft.com/azure/cosmos-db/create-cosmosdb-resources-portal) - ensure the [vector search](https://learn.microsoft.com/azure/cosmos-db/nosql/vector-search) feature is enabled and that you have created a database called "MultiAgentDemoDB".
- [Azure OpenAI API key](https://learn.microsoft.com/azure/ai-services/openai/overview) and endpoint.
- [Azure OpenAI Embedding Deployment ID](https://learn.microsoft.com/azure/ai-services/openai/overview) for the RAG model.
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) to authenticate to Azure Cosmos DB with [Entra ID RBAC](https://learn.microsoft.com/entra/identity/role-based-access-control/).

## How to run locally

Clone the repository:

```shell
git clone https://github.com/AzureCosmosDB/multi-agent-swarm
cd multi-agent-swarm
```

Install dependencies:

```shell
pip install git+https://github.com/openai/swarm.git
pip install azure-cosmos==4.9.0
pip install gradio
pip install azure-identity
```

Ensure you have the following environment variables set:
```shell
AZURE_COSMOSDB_ENDPOINT=your_cosmosdb_account_uri
AZURE_OPENAI_ENDPOINT=your_azure_openai_endpoint
AZURE_OPENAI_API_KEY=your_azure_openai_api_key
AZURE_OPENAI_EMBEDDINGDEPLOYMENTID=your_azure_openai_embeddingdeploymentid
```

Once you have installed dependencies, authenticate locally with the below command:

```shell
az login
```

If your signed-in Azure user does not already have access to Azure Cosmos DB via RBAC, run the below to retrieve your sign-in user (principal id): 

```bash
az ad signed-in-user show --query id -o tsv
```

Then run the below in Azure CLI shell (replace appropriate values) to create role assignment for Azure Cosmos DB:

```bash
# Bash (replace appropriate values)
az cosmosdb sql role assignment create \
--resource-group "<resource group>" \
--account-name "<Cosmos DB account name>" \
--role-definition-name "Cosmos DB Built-in Data Contributor" \
--principal-id "<principal id retrieved above>" \
--scope "/subscriptions/<subscription id>/resourceGroups/<resource group>/providers/Microsoft.DocumentDB/databaseAccounts/<cosmos account>"
```

Run below and click on URL provided in output:

```shell
python src/app/ai_chat_bot.py
```

To see the agent handoffs, you can also run as an interactive Swarm CLI session using:

```shell
python src/app/multi_agent_service.py
```