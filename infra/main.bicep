// -----------------------------------------------------------------------------
// main.bicep — resource-group-scoped deployment for the
// copilot-sdk-otel-foundry-demo. Entry point invoked by `azd up`.
//
// Provisions, in order:
//   1. Log Analytics workspace + workspace-based Application Insights
//   2. Azure AI Foundry account + project (App Insights linked to project)
//   3. Azure OpenAI account + gpt-4o-mini and text-embedding-3-small deployments
//   4. Azure AI Search (Basic SKU)
//   5. User-assigned managed identity + RBAC role assignments
//
// All concrete module bodies are stubbed in infra/modules/*.bicep and will be
// finalised by the coding session that runs `azd up`.
// -----------------------------------------------------------------------------

targetScope = 'resourceGroup'

@minLength(1)
@description('Primary location for all resources.')
param location string = resourceGroup().location

@minLength(1)
@maxLength(20)
@description('Short name used to build resource names. Lowercase, alphanumeric.')
param environmentName string = 'copilototeldemo'

@description('Object ID of the user / principal that should have data-plane roles on the demo resources (Foundry user, Search Index Data Reader, Cognitive Services OpenAI User).')
param principalId string

@description('Azure OpenAI chat model and deployment.')
param chatModelName string = 'gpt-4o-mini'
param chatModelVersion string = '2024-07-18'
param chatDeploymentName string = 'gpt-4o-mini'
param chatDeploymentCapacity int = 30

@description('Azure OpenAI embedding model and deployment.')
param embeddingModelName string = 'text-embedding-3-small'
param embeddingModelVersion string = '1'
param embeddingDeploymentName string = 'text-embedding-3-small'
param embeddingDeploymentCapacity int = 30

@description('Region for the Azure AI Search service. Defaulted to westus3 because Basic SKU capacity is currently exhausted in eastus2 and the eastus public data-plane endpoint is unreachable from some corporate VPN egress paths.')
param searchLocation string = 'westus3'

var resourceToken = uniqueString(subscription().id, resourceGroup().id, environmentName)
var tags = {
  'azd-env-name': environmentName
  workload: 'copilot-sdk-otel-foundry-demo'
  costCenter: 'demo'
}

// ---- Monitoring (Log Analytics + App Insights) -------------------------------
module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    location: location
    resourceToken: resourceToken
    tags: tags
  }
}

// ---- Azure AI Foundry account + project --------------------------------------
module foundry 'modules/foundry.bicep' = {
  name: 'foundry'
  params: {
    location: location
    resourceToken: resourceToken
    tags: tags
    applicationInsightsId: monitoring.outputs.applicationInsightsId
    applicationInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
  }
}

// ---- Azure OpenAI ------------------------------------------------------------
module openai 'modules/openai.bicep' = {
  name: 'openai'
  params: {
    location: location
    resourceToken: resourceToken
    tags: tags
    chatModelName: chatModelName
    chatModelVersion: chatModelVersion
    chatDeploymentName: chatDeploymentName
    chatDeploymentCapacity: chatDeploymentCapacity
    embeddingModelName: embeddingModelName
    embeddingModelVersion: embeddingModelVersion
    embeddingDeploymentName: embeddingDeploymentName
    embeddingDeploymentCapacity: embeddingDeploymentCapacity
  }
}

// ---- Azure AI Search (Basic) -------------------------------------------------
module search 'modules/search.bicep' = {
  name: 'search'
  params: {
    location: searchLocation
    resourceToken: resourceToken
    tags: tags
  }
}

// ---- RBAC --------------------------------------------------------------------
module rbac 'modules/rbac.bicep' = {
  name: 'rbac'
  params: {
    principalId: principalId
    searchServiceName: search.outputs.searchServiceName
    openAiAccountName: openai.outputs.openAiAccountName
    foundryAccountName: foundry.outputs.foundryAccountName
  }
}

// ---- Outputs (consumed by azd env / .env) ------------------------------------
output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = resourceGroup().name

output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.applicationInsightsConnectionString
output LOG_ANALYTICS_WORKSPACE_ID string = monitoring.outputs.logAnalyticsWorkspaceId

output AZURE_OPENAI_ENDPOINT string = openai.outputs.openAiEndpoint
output AZURE_OPENAI_CHAT_DEPLOYMENT string = chatDeploymentName
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT string = embeddingDeploymentName

output AZURE_AI_SEARCH_ENDPOINT string = search.outputs.searchEndpoint
output AZURE_AI_SEARCH_INDEX string = 'northwind-kb'

output AZURE_AI_FOUNDRY_ACCOUNT string = foundry.outputs.foundryAccountName
output AZURE_AI_PROJECT_NAME string = foundry.outputs.foundryProjectName
output AZURE_AI_PROJECT_ENDPOINT string = foundry.outputs.foundryProjectEndpoint
