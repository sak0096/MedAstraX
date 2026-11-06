targetScope = 'resourceGroup'

@description('Short lowercase deployment prefix.')
@minLength(3)
@maxLength(12)
param prefix string

@description('Azure region approved by Auburn IT.')
param location string = resourceGroup().location

@allowed([
  'dev'
  'test'
  'pilot'
])
param environmentName string = 'pilot'

@description('Immutable repository reference, for example medastrax@sha256:<digest>.')
param containerImageReference string
param postgresAdministratorLogin string

@secure()
param postgresAdministratorPassword string

@description('Runtime-role PostgreSQL URL created after least-privilege role setup.')
@secure()
param runtimeDatabaseUrl string

@secure()
param sessionSecret string

@secure()
param integrationSecret string

param entraTenantId string
param entraAudience string
param entraAdminRole string = 'MedAstraX.ResearchAdmin'
param recruitmentEnabled bool = false
param enrollmentNamespace string = 'test'
param retentionPolicy string = 'unresolved'
param paymentTutorialFailCents string = ''
param releaseManifestPath string = 'release/release-manifest.json'
param postgresSkuName string = 'Standard_D2ds_v5'
param postgresTier string = 'GeneralPurpose'
param postgresStorageGb int = 128
param postgresBackupRetentionDays int = 14
param webAppSkuName string = 'P1v3'
param monthlyBudgetAmount int = 500
param budgetStartDate string
param budgetContactEmails array = []

var stem = toLower('${prefix}-${environmentName}')
var compact = take(replace(uniqueString(subscription().id, resourceGroup().id, stem), '-', ''), 10)
var acrName = take(replace('${prefix}${environmentName}${compact}', '-', ''), 50)
var storageName = take(replace('${prefix}${environmentName}${compact}', '-', ''), 24)
var vaultName = take('${stem}-${compact}', 24)
var postgresName = take('${stem}-pg-${compact}', 63)
var appName = take('${stem}-app-${compact}', 60)

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${stem}-logs'
  location: location
  properties: {
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${stem}-insights'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspace.id
    DisableIpMasking: false
  }
}

resource network 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: '${stem}-vnet'
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.42.0.0/16'
      ]
    }
    subnets: [
      {
        name: 'app-integration'
        properties: {
          addressPrefix: '10.42.1.0/24'
          delegations: [
            {
              name: 'web'
              properties: {
                serviceName: 'Microsoft.Web/serverFarms'
              }
            }
          ]
        }
      }
      {
        name: 'postgres'
        properties: {
          addressPrefix: '10.42.2.0/24'
          delegations: [
            {
              name: 'postgres'
              properties: {
                serviceName: 'Microsoft.DBforPostgreSQL/flexibleServers'
              }
            }
          ]
        }
      }
      {
        name: 'private-endpoints'
        properties: {
          addressPrefix: '10.42.3.0/24'
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

resource appSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' existing = {
  parent: network
  name: 'app-integration'
}

resource postgresSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' existing = {
  parent: network
  name: 'postgres'
}

resource privateEndpointSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' existing = {
  parent: network
  name: 'private-endpoints'
}

resource postgresDns 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.postgres.database.azure.com'
  location: 'global'
}

resource postgresDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: postgresDns
  name: '${stem}-postgres-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: network.id
    }
  }
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: postgresName
  location: location
  sku: {
    name: postgresSkuName
    tier: postgresTier
  }
  properties: {
    version: '16'
    administratorLogin: postgresAdministratorLogin
    administratorLoginPassword: postgresAdministratorPassword
    storage: {
      storageSizeGB: postgresStorageGb
      autoGrow: 'Enabled'
    }
    backup: {
      backupRetentionDays: postgresBackupRetentionDays
      geoRedundantBackup: 'Disabled'
    }
    network: {
      delegatedSubnetResourceId: postgresSubnet.id
      privateDnsZoneArmResourceId: postgresDns.id
      publicNetworkAccess: 'Disabled'
    }
    highAvailability: {
      mode: environmentName == 'pilot' ? 'ZoneRedundant' : 'Disabled'
    }
  }
  dependsOn: [
    postgresDnsLink
  ]
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgres
  name: 'medastrax'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  #disable-next-line BCP334
  name: acrName
  location: location
  sku: {
    name: 'Premium'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Disabled'
    zoneRedundancy: environmentName == 'pilot' ? 'Enabled' : 'Disabled'
  }
}

resource blob 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  #disable-next-line BCP334
  name: storageName
  location: location
  sku: {
    name: 'Standard_ZRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Disabled'
    supportsHttpsTrafficOnly: true
  }
}

resource artifacts 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  name: '${blob.name}/default/release-artifacts'
  properties: {
    publicAccess: 'None'
    immutableStorageWithVersioning: {
      enabled: true
    }
  }
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: vaultName
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enablePurgeProtection: true
    enableSoftDelete: true
    publicNetworkAccess: 'Disabled'
    softDeleteRetentionInDays: 90
  }
}

resource databaseUrlSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'database-url'
  properties: {
    value: runtimeDatabaseUrl
  }
}

resource sessionSecretResource 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'session-secret'
  properties: {
    value: sessionSecret
  }
}

resource integrationSecretResource 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'integration-secret'
  properties: {
    value: integrationSecret
  }
}

resource registryEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: '${stem}-acr-pe'
  location: location
  properties: {
    subnet: {
      id: privateEndpointSubnet.id
    }
    privateLinkServiceConnections: [
      {
        name: 'registry'
        properties: {
          privateLinkServiceId: registry.id
          groupIds: [
            'registry'
          ]
        }
      }
    ]
  }
}

resource blobEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: '${stem}-blob-pe'
  location: location
  properties: {
    subnet: {
      id: privateEndpointSubnet.id
    }
    privateLinkServiceConnections: [
      {
        name: 'blob'
        properties: {
          privateLinkServiceId: blob.id
          groupIds: [
            'blob'
          ]
        }
      }
    ]
  }
}

resource vaultEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: '${stem}-vault-pe'
  location: location
  properties: {
    subnet: {
      id: privateEndpointSubnet.id
    }
    privateLinkServiceConnections: [
      {
        name: 'vault'
        properties: {
          privateLinkServiceId: vault.id
          groupIds: [
            'vault'
          ]
        }
      }
    ]
  }
}

resource registryDns 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.azurecr.io'
  location: 'global'
}

resource blobDns 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.blob.${environment().suffixes.storage}'
  location: 'global'
}

resource vaultDns 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.vaultcore.azure.net'
  location: 'global'
}

resource registryDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: registryDns
  name: '${stem}-registry-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: network.id
    }
  }
}

resource blobDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: blobDns
  name: '${stem}-blob-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: network.id
    }
  }
}

resource vaultDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: vaultDns
  name: '${stem}-vault-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: network.id
    }
  }
}

resource registryDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: registryEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'registry'
        properties: {
          privateDnsZoneId: registryDns.id
        }
      }
    ]
  }
}

resource blobDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: blobEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'blob'
        properties: {
          privateDnsZoneId: blobDns.id
        }
      }
    ]
  }
}

resource vaultDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: vaultEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'vault'
        properties: {
          privateDnsZoneId: vaultDns.id
        }
      }
    ]
  }
}

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${stem}-plan'
  location: location
  kind: 'linux'
  sku: {
    name: webAppSkuName
  }
  properties: {
    reserved: true
    zoneRedundant: environmentName == 'pilot'
  }
}

resource app 'Microsoft.Web/sites@2023-12-01' = {
  name: appName
  location: location
  kind: 'app,linux,container'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    publicNetworkAccess: 'Enabled'
    virtualNetworkSubnetId: appSubnet.id
    siteConfig: {
      alwaysOn: true
      ftpsState: 'Disabled'
      http20Enabled: true
      linuxFxVersion: 'DOCKER|${registry.properties.loginServer}/${containerImageReference}'
      minimumElasticInstanceCount: environmentName == 'pilot' ? 2 : 1
      healthCheckPath: '/health/live'
      vnetRouteAllEnabled: true
      acrUseManagedIdentityCreds: true
      appSettings: [
        {
          name: 'HC_ENVIRONMENT'
          value: 'production'
        }
        {
          name: 'HC_STORAGE_BACKEND'
          value: 'postgres'
        }
        {
          name: 'HC_DATABASE_URL'
          value: '@Microsoft.KeyVault(SecretUri=${databaseUrlSecret.properties.secretUriWithVersion})'
        }
        {
          name: 'HC_SESSION_SECRET'
          value: '@Microsoft.KeyVault(SecretUri=${sessionSecretResource.properties.secretUriWithVersion})'
        }
        {
          name: 'HC_INTEGRATION_SECRET'
          value: '@Microsoft.KeyVault(SecretUri=${integrationSecretResource.properties.secretUriWithVersion})'
        }
        {
          name: 'HC_ENTRA_TENANT_ID'
          value: entraTenantId
        }
        {
          name: 'HC_ENTRA_AUDIENCE'
          value: entraAudience
        }
        {
          name: 'HC_ENTRA_ADMIN_ROLE'
          value: entraAdminRole
        }
        {
          name: 'HC_RECRUITMENT_ENABLED'
          value: string(recruitmentEnabled)
        }
        {
          name: 'HC_ENROLLMENT_NAMESPACE'
          value: enrollmentNamespace
        }
        {
          name: 'HC_RETENTION_POLICY'
          value: retentionPolicy
        }
        {
          name: 'HC_PAYMENT_TUTORIAL_FAIL_CENTS'
          value: paymentTutorialFailCents
        }
        {
          name: 'HC_RELEASE_MANIFEST_PATH'
          value: releaseManifestPath
        }
        {
          name: 'HC_STUDY_MODE'
          value: 'true'
        }
        {
          name: 'HC_ENFORCE_PROGRESSION'
          value: 'true'
        }
        {
          name: 'HC_ALLOW_SYNTHETIC_LAUNCH'
          value: 'false'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: insights.properties.ConnectionString
        }
        {
          name: 'WEBSITES_PORT'
          value: '8000'
        }
        {
          name: 'WEBSITE_PULL_IMAGE_OVER_VNET'
          value: 'true'
        }
      ]
    }
  }
  dependsOn: [
    registryDnsGroup
    blobDnsGroup
    vaultDnsGroup
  ]
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, app.id, 'acrpull')
  scope: registry
  properties: {
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '7f951dda-4ed3-4680-a7ca-43fe172d538d'
    )
  }
}

resource vaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, app.id, 'secrets-user')
  scope: vault
  properties: {
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '4633458b-17de-408a-b874-0445c86b69e6'
    )
  }
}

resource blobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(blob.id, app.id, 'blob-contributor')
  scope: blob
  properties: {
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    )
  }
}

resource appDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'log-analytics'
  scope: app
  properties: {
    workspaceId: workspace.id
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

resource postgresDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'log-analytics'
  scope: postgres
  properties: {
    workspaceId: workspace.id
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: '${stem}-monthly-budget'
  properties: {
    amount: monthlyBudgetAmount
    category: 'Cost'
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: budgetStartDate
    }
    notifications: {
      forecast80: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 80
        thresholdType: 'Forecasted'
        contactEmails: budgetContactEmails
        contactGroups: []
        contactRoles: []
      }
      actual100: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 100
        thresholdType: 'Actual'
        contactEmails: budgetContactEmails
        contactGroups: []
        contactRoles: []
      }
    }
  }
}

output webAppName string = app.name
output webAppHost string = app.properties.defaultHostName
output registryName string = registry.name
output postgresServerName string = postgres.name
output keyVaultName string = vault.name
output storageAccountName string = blob.name
