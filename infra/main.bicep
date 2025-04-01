metadata description = 'Provisions resources for the multi-agent-swarm sample application that uses Azure Cosmos DB for NoSQL and Azure OpenAI.'

targetScope = 'resourceGroup'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention.')
param environmentName string

@minLength(1)
@description('Primary location for all resources.')
param location string

@description('Id of the principal to assign database and application roles.')
param deploymentUserPrincipalId string = ''

// serviceName is used as value for the tag (azd-service-name) azd uses to identify deployment host
param serviceName string = 'swarm'

var resourceToken = toLower(uniqueString(resourceGroup().id, environmentName, location))
var tags = {
  'azd-env-name': environmentName
  repo: 'https://github.com/azurecosmosdb/multi-agent-swarm'
}

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'managed-identity-${resourceToken}'
  location: location
  tags: tags
}

resource cosmosDbAccount 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' = {
  name: 'cosmos-db-nosql-${resourceToken}'
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    disableKeyBasedMetadataWriteAccess: true
    publicNetworkAccess: 'Enabled'
    ipRules: []
    virtualNetworkRules: []
    capabilities: [
      {
        name: 'EnableServerless'
      }
      {
        name: 'EnableNoSQLVectorSearch'
      }
    ]
  }
  tags: tags
}

resource sqlRoleDefinition 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2024-11-15' = {
  name: guid('nosql-data-plane-contributor', environmentName)
  parent: cosmosDbAccount
  properties: {
    roleName: 'nosql-data-plane-contributor'
    type: 'CustomRole'
    assignableScopes: [
      cosmosDbAccount.id
    ]
    permissions: [
      {
        dataActions: [
          'Microsoft.DocumentDB/databaseAccounts/readMetadata'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/*'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/*'
        ]
      }
    ]
  }
}

resource sqlRoleAssignmentMI 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = {
  parent: cosmosDbAccount
  name: guid('nosql-data-plane-contributor-mi', environmentName)
  properties: {
    roleDefinitionId: sqlRoleDefinition.id
    principalId: managedIdentity.properties.principalId
    scope: cosmosDbAccount.id
  }
}

resource sqlRoleAssignmentSP 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = {
  parent: cosmosDbAccount
  name: guid('nosql-data-plane-contributor-sp', environmentName)
  properties: {
    roleDefinitionId: sqlRoleDefinition.id
    principalId: deploymentUserPrincipalId
    scope: cosmosDbAccount.id
  }
}

resource sqlDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-11-15' = {
  parent: cosmosDbAccount
  name: 'MultiAgentDemoDB'
  properties: {
    resource: {
      id: 'MultiAgentDemoDB'
    }
  }
}

resource sqlContainerUsers 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = {
  parent: sqlDatabase
  name: 'Users'
  properties: {
    resource: {
      id: 'Users'
      partitionKey: {
        paths: ['/user_id']
        kind: 'Hash'
      }
    }
  }
}

resource sqlContainerPurchaseHistory 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = {
  parent: sqlDatabase
  name: 'PurchaseHistory'
  properties: {
    resource: {
      id: 'PurchaseHistory'
      partitionKey: {
        paths: ['/user_id']
        kind: 'Hash'
      }
    }
  }
}

resource sqlContainerChat 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = {
  parent: sqlDatabase
  name: 'Chat'
  properties: {
    resource: {
      id: 'Chat'
      partitionKey: {
        paths: ['/user_id', '/session_id']
        kind: 'MultiHash'
      }
    }
  }
}

resource sqlContainerProducts 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = {
  parent: sqlDatabase
  name: 'Products'
  properties: {
    resource: {
      id: 'Products'
      partitionKey: {
        paths: ['/product_id']
        kind: 'Hash'
      }
      indexingPolicy: {
        automatic: true
        indexingMode: 'consistent'
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: []
        vectorIndexes: [
          {
            path: '/product_description_vector'
            type: 'diskANN'
          }
        ]
      }
      vectorEmbeddingPolicy: {
        vectorEmbeddings: [
          {
            path: '/product_description_vector'
            distanceFunction: 'cosine'
            dataType: 'float32'
            dimensions: 1536
          }
        ]
      }
    }
  }
}

resource openAI 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: 'open-ai-${resourceToken}'
  location: location
  kind: 'OpenAI'
  properties: {
    disableLocalAuth: true
    customSubDomainName: 'open-ai-${resourceToken}'
    publicNetworkAccess: 'Enabled'
  }
  sku: {
    name: 'S0'
  }
  tags: tags
}

resource openAIEmbeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = {
  parent: openAI
  name: 'text-embedding-3-large'
  sku: {
    name: 'Standard'
    capacity: 5
  }
  properties: {
    model: {
      name: 'text-embedding-3-large'
      format: 'OpenAI'
      version: '1'
    }
  }
}

resource openAIGPTDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = {
  parent: openAI
  name: 'gpt-4o-mini'
  sku: {
    name: 'GlobalStandard'
    capacity: 40
  }
  properties: {
    model: {
      name: 'gpt-4o-mini'
      format: 'OpenAI'
      version: '2024-07-18'
    }
  }
}

resource openAIassignmentUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid('open-ai-assignment-user', environmentName)
  scope: resourceGroup()
  properties: {
    principalId: deploymentUserPrincipalId
    // Cognitive Services OpenAI User built-in role
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalType: 'User'
  }
}

resource openAIassignmentMI 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid('open-ai-assignment-mi', environmentName)
  scope: resourceGroup()
  properties: {
    principalId: managedIdentity.properties.principalId
    // Cognitive Services OpenAI User built-in role
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalType: 'ServicePrincipal'
  }
}


// Environment file outputs
output AZURE_COSMOSDB_ENDPOINT string = cosmosDbAccount.properties.documentEndpoint
output AZURE_OPENAI_ENDPOINT string = openAI.properties.endpoint
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT string = openAIEmbeddingDeployment.name
output AZURE_OPENAI_GPT_DEPLOYMENT string = openAIGPTDeployment.name
