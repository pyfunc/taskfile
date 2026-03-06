# IaC Bicep — Azure Infrastructure + Markpact

**Cały projekt Azure Bicep w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

Azure Bicep — deklaratywny język IaC dla Azure. Natywny następca ARM Templates.
Multi-environment (dev/staging/prod), what-if preview, zintegrowane z `taskfile`.

## Features covered

- **`env_file`** — per-environment Azure subscription config
- **`deps`** — lint + validate before deploy
- **`condition`** — bicep CLI availability check
- **`environment_groups`** — `all-prod` for rolling deployment
- **What-if** — preview changes before deploy

## 🎯 Workflow

```bash
# 1. Wypakowanie projektu
markpact README.md && cd sandbox

# 2. Login do Azure
taskfile run login

# 3. Lint + validate
taskfile --env dev run lint
taskfile --env dev run validate

# 4. What-if preview
taskfile --env dev run what-if

# 5. Deploy
taskfile --env dev run deploy
taskfile --env prod run deploy

# 6. Outputs
taskfile --env dev run outputs

# 7. Destroy
taskfile --env dev run destroy
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run login` | Login to Azure CLI |
| `taskfile run lint` | Lint Bicep files |
| `taskfile run validate` | Validate deployment |
| `taskfile run what-if` | Preview changes (what-if) |
| `taskfile run deploy` | Deploy to Azure |
| `taskfile run outputs` | Show deployment outputs |
| `taskfile run destroy` | Delete resource group |
| `taskfile run build` | Compile Bicep to ARM JSON |
| `taskfile run decompile` | Convert ARM JSON to Bicep |
| `taskfile run clean` | Remove compiled files |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: bicep-infra
description: "Azure Bicep: multi-env infrastructure deployment with what-if"

variables:
  BICEP_DIR: bicep
  MAIN_FILE: main.bicep
  LOCATION: westeurope
  RG_PREFIX: myapp

environments:
  dev:
    env_file: .env.dev
    variables:
      RESOURCE_GROUP: ${RG_PREFIX}-dev-rg
      LOCATION: westeurope
      SKU: Standard_B1s
      ENV_TAG: dev
      SUBSCRIPTION: dev-subscription-id

  staging:
    env_file: .env.staging
    variables:
      RESOURCE_GROUP: ${RG_PREFIX}-staging-rg
      LOCATION: westeurope
      SKU: Standard_B2s
      ENV_TAG: staging
      SUBSCRIPTION: staging-subscription-id

  prod:
    env_file: .env.prod
    variables:
      RESOURCE_GROUP: ${RG_PREFIX}-prod-rg
      LOCATION: westeurope
      SKU: Standard_D2s_v3
      ENV_TAG: prod
      SUBSCRIPTION: prod-subscription-id

environment_groups:
  all-prod:
    members: [prod]
    strategy: rolling
    max_parallel: 1

tasks:

  login:
    desc: Login to Azure CLI
    cmds:
      - az login
      - az account set --subscription ${SUBSCRIPTION}

  lint:
    desc: Lint Bicep files
    dir: ${BICEP_DIR}
    cmds:
      - az bicep lint --file ${MAIN_FILE}
    ignore_errors: true

  validate:
    desc: Validate deployment
    dir: ${BICEP_DIR}
    cmds:
      - >-
        az deployment group validate
        --resource-group ${RESOURCE_GROUP}
        --template-file ${MAIN_FILE}
        --parameters environment=${ENV_TAG} vmSize=${SKU} location=${LOCATION}

  what-if:
    desc: Preview changes (what-if deployment)
    dir: ${BICEP_DIR}
    cmds:
      - >-
        az deployment group what-if
        --resource-group ${RESOURCE_GROUP}
        --template-file ${MAIN_FILE}
        --parameters environment=${ENV_TAG} vmSize=${SKU} location=${LOCATION}

  deploy:
    desc: Deploy Bicep to Azure
    dir: ${BICEP_DIR}
    deps: [lint]
    cmds:
      - az group create --name ${RESOURCE_GROUP} --location ${LOCATION}
      - >-
        az deployment group create
        --resource-group ${RESOURCE_GROUP}
        --template-file ${MAIN_FILE}
        --parameters environment=${ENV_TAG} vmSize=${SKU} location=${LOCATION}
        --name taskfile-deploy-$(date +%Y%m%d%H%M%S)

  outputs:
    desc: Show deployment outputs
    cmds:
      - >-
        az deployment group show
        --resource-group ${RESOURCE_GROUP}
        --name $(az deployment group list --resource-group ${RESOURCE_GROUP} --query '[0].name' -o tsv)
        --query properties.outputs

  destroy:
    desc: Delete resource group and all resources
    cmds:
      - az group delete --name ${RESOURCE_GROUP} --yes --no-wait

  build:
    desc: Compile Bicep to ARM JSON
    dir: ${BICEP_DIR}
    cmds:
      - az bicep build --file ${MAIN_FILE} --outfile main.json

  decompile:
    desc: Convert ARM JSON to Bicep
    dir: ${BICEP_DIR}
    cmds:
      - az bicep decompile --file main.json

  clean:
    desc: Remove compiled ARM templates
    dir: ${BICEP_DIR}
    cmds:
      - rm -f *.json
```

### bicep/main.bicep — Azure Bicep template

```markpact:file path=bicep/main.bicep
@description('Environment name')
param environment string

@description('Azure region')
param location string = resourceGroup().location

@description('VM size')
param vmSize string = 'Standard_B1s'

// Virtual Network
resource vnet 'Microsoft.Network/virtualNetworks@2023-09-01' = {
  name: '${environment}-vnet'
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: ['10.0.0.0/16']
    }
    subnets: [
      {
        name: 'default'
        properties: {
          addressPrefix: '10.0.1.0/24'
        }
      }
      {
        name: 'app'
        properties: {
          addressPrefix: '10.0.2.0/24'
        }
      }
    ]
  }
  tags: {
    Environment: environment
    ManagedBy: 'bicep-taskfile'
  }
}

// Network Security Group
resource nsg 'Microsoft.Network/networkSecurityGroups@2023-09-01' = {
  name: '${environment}-nsg'
  location: location
  properties: {
    securityRules: [
      {
        name: 'AllowHTTP'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '80'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'AllowHTTPS'
        properties: {
          priority: 110
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '443'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

output vnetId string = vnet.id
output vnetName string = vnet.name
output nsgId string = nsg.id
```

### .env.dev

```markpact:file path=.env.dev
AZURE_SUBSCRIPTION_ID=your-dev-subscription-id
```

---

## 📚 Dokumentacja

- [Azure Bicep Docs](https://learn.microsoft.com/azure/azure-resource-manager/bicep/)
- [Bicep Playground](https://aka.ms/bicepdemo)
- [Bicep Examples](https://github.com/Azure/bicep/tree/main/docs/examples)

**Licencja:** MIT
