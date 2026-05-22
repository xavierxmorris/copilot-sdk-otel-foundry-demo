// rbac.bicep — least-privilege role assignments for the demo principal.

@description('Object ID of the user / service principal running the Python app.')
param principalId string

param searchServiceName string
param openAiAccountName string
param foundryAccountName string

// Role definition IDs (well-known GUIDs).
var roles = {
  // Search Index Data Reader (read documents from indexes)
  searchIndexDataReader: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
  // Search Index Data Contributor (read/write documents — needed by seed_index.py upload_documents)
  searchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
  // Search Service Contributor (create/update indexes from seed_index.py)
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
  // Cognitive Services OpenAI User
  cognitiveServicesOpenAiUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  // Monitoring Metrics Publisher (for OTel export to App Insights)
  monitoringMetricsPublisher: '3913510d-42f4-4e42-8a64-420c390055eb'
  // Azure AI Developer (Foundry project user)
  azureAiDeveloper: '64702f94-c441-49e6-a78b-ef80e0188fee'
}

resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' existing = {
  name: searchServiceName
}
resource openAi 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: openAiAccountName
}
resource foundry 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: foundryAccountName
}

resource raSearchReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, principalId, roles.searchIndexDataReader)
  scope: searchService
  properties: {
    principalId: principalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchIndexDataReader)
  }
}

resource raSearchContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, principalId, roles.searchServiceContributor)
  scope: searchService
  properties: {
    principalId: principalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchServiceContributor)
  }
}

resource raSearchDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, principalId, roles.searchIndexDataContributor)
  scope: searchService
  properties: {
    principalId: principalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchIndexDataContributor)
  }
}

resource raOpenAi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAi.id, principalId, roles.cognitiveServicesOpenAiUser)
  scope: openAi
  properties: {
    principalId: principalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cognitiveServicesOpenAiUser)
  }
}

resource raFoundryDev 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, principalId, roles.azureAiDeveloper)
  scope: foundry
  properties: {
    principalId: principalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.azureAiDeveloper)
  }
}
