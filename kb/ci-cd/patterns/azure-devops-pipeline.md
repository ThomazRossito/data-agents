# Azure DevOps Pipeline para Databricks

## Estrutura de Pipeline Recomendada
```
azure-pipelines/
├── dev_to_test.yml      ← PR dev → test dispara este pipeline
└── test_to_main.yml     ← PR test → main dispara este pipeline
```

## dev_to_test.yml
```yaml
trigger:
  branches:
    include:
      - test
      - staging

pool:
  vmImage: ubuntu-latest

variables:
  - group: databricks-staging-vars  # variáveis de grupo no Azure DevOps

stages:
  - stage: Validate
    jobs:
      - job: validate_bundle
        steps:
          - task: UsePythonVersion@0
            inputs:
              versionSpec: "3.11"
          - script: |
              pip install databricks-cli databricks-sdk
              databricks bundle validate -t staging
            displayName: "Validate Bundle"
            env:
              DATABRICKS_HOST: $(DATABRICKS_STAGING_HOST)
              DATABRICKS_TOKEN: $(DATABRICKS_STAGING_TOKEN)

  - stage: Deploy
    dependsOn: Validate
    jobs:
      - deployment: deploy_staging
        environment: staging
        strategy:
          runOnce:
            deploy:
              steps:
                - script: |
                    databricks bundle deploy -t staging --auto-approve
                  displayName: "Deploy to Staging"
                  env:
                    DATABRICKS_HOST: $(DATABRICKS_STAGING_HOST)
                    DATABRICKS_TOKEN: $(DATABRICKS_STAGING_TOKEN)

  - stage: SmokeTest
    dependsOn: Deploy
    jobs:
      - job: run_smoke_test
        steps:
          - script: |
              databricks bundle run smoke_test_job -t staging
            displayName: "Run Smoke Test"
```

## test_to_main.yml
```yaml
trigger:
  branches:
    include:
      - main

stages:
  - stage: DeployProd
    jobs:
      - deployment: deploy_prod
        environment: production  # requer aprovação manual no Azure DevOps
        strategy:
          runOnce:
            deploy:
              steps:
                - script: |
                    databricks bundle deploy -t prod --auto-approve
                  env:
                    DATABRICKS_HOST: $(DATABRICKS_PROD_HOST)
                    DATABRICKS_TOKEN: $(DATABRICKS_PROD_TOKEN)
```

## Variáveis de Grupo — Configurar no Azure DevOps
```
Library → Variable Groups → databricks-staging-vars:
  DATABRICKS_STAGING_HOST = https://staging.azuredatabricks.net
  DATABRICKS_STAGING_TOKEN = (secret) ****
  AZURE_SP_CLIENT_ID = (secret) ****
  AZURE_SP_SECRET = (secret) ****
```

## Service Connection
```
Project Settings → Service Connections → Azure Resource Manager
  → Service Principal (automatic) ou Manual (para SP pré-criado)
  → Scope: Subscription ou Resource Group
```
