// search.bicep — Azure AI Search (Basic SKU) for the RAG retrieval store.

@description('Region for the Search service. Defaults to the resource group location, but can be overridden if Basic capacity is exhausted in the primary region.')
param location string
param resourceToken string
param tags object

var searchServiceName = 'srch-${resourceToken}'

resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: searchServiceName
  location: location
  tags: tags
  sku: {
    name: 'basic'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
    semanticSearch: 'free'
  }
}

output searchServiceName string = searchService.name
output searchEndpoint string = 'https://${searchService.name}.search.windows.net'
