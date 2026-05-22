// foundry.bicep — Azure AI Foundry account + project, with App Insights linked.
//
// NOTE: The Foundry resource provider API surface evolves rapidly. This module
// uses Microsoft.CognitiveServices/accounts with kind=AIServices (the
// current Foundry packaging) and the projects child resource.
// The coding session will validate the API versions against the latest
// `az rest --method get` of the resource at deploy time.

param location string
param resourceToken string
param tags object

@description('Resource ID of the Application Insights to link to the Foundry project.')
param applicationInsightsId string

@description('Connection string for the Application Insights resource (used as the connection credential).')
@secure()
param applicationInsightsConnectionString string

var foundryAccountName = 'aif-${resourceToken}'
var foundryProjectName = 'proj-copilot-otel-demo'

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: foundryAccountName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: foundryAccountName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: foundryAccount
  name: foundryProjectName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: 'Copilot SDK OTel demo'
    description: 'Foundry project for the Copilot SDK -> OTel -> App Insights -> Foundry tracing & evaluation demo.'
  }
}

// Link the Application Insights resource to the Foundry project so the
// Tracing tab and Evaluation-from-Traces pick it up automatically.
//
// The Foundry "AppInsights" project connection uses category=AppInsights with
// the App Insights connection string as the credential and the resource ID in
// metadata. This matches the connection that the Foundry portal creates when
// you click "Connect Application Insights" in the Tracing tab.
resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: foundryProject
  name: 'appinsights-connection'
  properties: {
    category: 'AppInsights'
    target: applicationInsightsId
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: applicationInsightsConnectionString
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: applicationInsightsId
    }
  }
}

output foundryAccountName string = foundryAccount.name
output foundryProjectName string = foundryProject.name
output foundryProjectEndpoint string = foundryAccount.properties.endpoint
