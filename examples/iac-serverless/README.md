# IaC Serverless Framework — FaaS Deployment + Markpact

**Cały projekt Serverless Framework w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

Serverless Framework — deploy funkcji Lambda/Cloud Functions/Azure Functions.
Multi-provider (AWS/GCP/Azure), multi-stage, zintegrowane z `taskfile`.

## Features covered

- **`dir`** — tasks run inside `serverless/` directory
- **`env_file`** — per-stage credentials
- **Multi-stage** — dev, staging, prod
- **Multi-provider** — AWS Lambda, GCP Cloud Functions
- **`deps`** — test before deploy

## 🎯 Workflow

```bash
# 1. Wypakowanie projektu
markpact README.md && cd sandbox

# 2. Instalacja
taskfile run install

# 3. Deploy dev
taskfile --env dev run deploy

# 4. Invoke function
taskfile --env dev run invoke --var FUNCTION=hello

# 5. Logs
taskfile --env dev run logs --var FUNCTION=hello

# 6. Deploy prod
taskfile --env prod run deploy

# 7. Remove
taskfile --env dev run remove
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run install` | Install Serverless + plugins |
| `taskfile run deploy` | Deploy all functions |
| `taskfile run deploy-function` | Deploy single function |
| `taskfile run remove` | Remove deployed stack |
| `taskfile run invoke` | Invoke function remotely |
| `taskfile run invoke-local` | Invoke function locally |
| `taskfile run logs` | View function logs |
| `taskfile run info` | Show service info |
| `taskfile run metrics` | Show function metrics |
| `taskfile run test` | Run tests |
| `taskfile run package` | Package without deploying |
| `taskfile run clean` | Remove .serverless directory |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: serverless-app
description: "Serverless Framework: multi-stage Lambda/Cloud Functions deployment"

variables:
  SLS_DIR: serverless
  SERVICE_NAME: my-api
  FUNCTION: hello
  RUNTIME: python3.12

environments:
  dev:
    env_file: .env.dev
    variables:
      STAGE: dev
      AWS_REGION: eu-west-1
      MEMORY_SIZE: "128"
      TIMEOUT: "10"

  staging:
    env_file: .env.staging
    variables:
      STAGE: staging
      AWS_REGION: eu-west-1
      MEMORY_SIZE: "256"
      TIMEOUT: "15"

  prod:
    env_file: .env.prod
    variables:
      STAGE: prod
      AWS_REGION: eu-west-1
      MEMORY_SIZE: "512"
      TIMEOUT: "30"

tasks:

  install:
    desc: Install Serverless Framework and plugins
    dir: ${SLS_DIR}
    cmds:
      - npm install -g serverless
      - npm install
      - pip install -r requirements.txt -t vendor/

  deploy:
    desc: Deploy all functions to stage
    dir: ${SLS_DIR}
    deps: [test]
    cmds:
      - serverless deploy --stage ${STAGE} --region ${AWS_REGION}

  deploy-function:
    desc: Deploy single function (use --var FUNCTION=name)
    dir: ${SLS_DIR}
    cmds:
      - serverless deploy function -f ${FUNCTION} --stage ${STAGE} --region ${AWS_REGION}

  remove:
    desc: Remove entire deployed stack
    dir: ${SLS_DIR}
    cmds:
      - serverless remove --stage ${STAGE} --region ${AWS_REGION}

  invoke:
    desc: Invoke function remotely (use --var FUNCTION=name)
    dir: ${SLS_DIR}
    cmds:
      - serverless invoke -f ${FUNCTION} --stage ${STAGE} --region ${AWS_REGION} --log

  invoke-local:
    desc: Invoke function locally
    dir: ${SLS_DIR}
    cmds:
      - serverless invoke local -f ${FUNCTION} --data '{"test": true}'

  logs:
    desc: View function logs (use --var FUNCTION=name)
    dir: ${SLS_DIR}
    cmds:
      - serverless logs -f ${FUNCTION} --stage ${STAGE} --region ${AWS_REGION} --tail

  info:
    desc: Show service info (endpoints, functions)
    dir: ${SLS_DIR}
    cmds:
      - serverless info --stage ${STAGE} --region ${AWS_REGION}

  metrics:
    desc: Show function metrics
    dir: ${SLS_DIR}
    cmds:
      - serverless metrics -f ${FUNCTION} --stage ${STAGE} --region ${AWS_REGION}

  test:
    desc: Run tests
    dir: ${SLS_DIR}
    cmds:
      - pytest tests/ -v

  package:
    desc: Package without deploying
    dir: ${SLS_DIR}
    cmds:
      - serverless package --stage ${STAGE} --region ${AWS_REGION}

  clean:
    desc: Remove .serverless directory and vendor
    dir: ${SLS_DIR}
    cmds:
      - rm -rf .serverless/ vendor/ node_modules/
      - rm -f package-lock.json
```

### serverless/serverless.yml — Serverless config

```markpact:file path=serverless/serverless.yml
service: my-api

frameworkVersion: '3'

provider:
  name: aws
  runtime: python3.12
  stage: ${opt:stage, 'dev'}
  region: ${opt:region, 'eu-west-1'}
  memorySize: ${self:custom.memorySize.${self:provider.stage}}
  timeout: ${self:custom.timeout.${self:provider.stage}}
  environment:
    STAGE: ${self:provider.stage}
  iam:
    role:
      statements:
        - Effect: Allow
          Action:
            - dynamodb:GetItem
            - dynamodb:PutItem
            - dynamodb:Query
          Resource: !GetAtt MainTable.Arn

custom:
  memorySize:
    dev: 128
    staging: 256
    prod: 512
  timeout:
    dev: 10
    staging: 15
    prod: 30

functions:
  hello:
    handler: handler.hello
    events:
      - httpApi:
          path: /hello
          method: get

  create:
    handler: handler.create
    events:
      - httpApi:
          path: /items
          method: post

resources:
  Resources:
    MainTable:
      Type: AWS::DynamoDB::Table
      Properties:
        TableName: ${self:service}-${self:provider.stage}
        BillingMode: PAY_PER_REQUEST
        AttributeDefinitions:
          - AttributeName: id
            AttributeType: S
        KeySchema:
          - AttributeName: id
            KeyType: HASH
```

### serverless/handler.py

```markpact:file path=serverless/handler.py
"""Lambda function handlers."""
import json
import os
import uuid


def hello(event, context):
    """Hello endpoint."""
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Hello from Serverless!",
            "stage": os.environ.get("STAGE", "unknown"),
        }),
    }


def create(event, context):
    """Create item endpoint."""
    body = json.loads(event.get("body", "{}"))
    item_id = str(uuid.uuid4())
    return {
        "statusCode": 201,
        "body": json.dumps({
            "id": item_id,
            "data": body,
        }),
    }
```

### serverless/requirements.txt

```markpact:file path=serverless/requirements.txt
boto3>=1.34.0
```

### .env.dev

```markpact:file path=.env.dev
AWS_PROFILE=serverless-dev
AWS_DEFAULT_REGION=eu-west-1
```

---

## 📚 Dokumentacja

- [Serverless Framework Docs](https://www.serverless.com/framework/docs)
- [AWS Lambda](https://docs.aws.amazon.com/lambda/)
- [Serverless Examples](https://github.com/serverless/examples)

**Licencja:** MIT
