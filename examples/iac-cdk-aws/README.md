# IaC AWS CDK — Cloud Development Kit + Markpact

**Cały projekt AWS CDK w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

AWS Cloud Development Kit — definiuj infrastrukturę w TypeScript/Python.
Multi-environment (dev/staging/prod), synth/diff/deploy z integracją `taskfile`.

## Features covered

- **`dir`** — tasks run inside `cdk/` directory
- **`env_file`** — per-environment AWS credentials
- **`deps`** — synth before deploy
- **`condition`** — cdk installed check

## 🎯 Workflow

```bash
# 1. Wypakowanie projektu
markpact README.md && cd sandbox

# 2. Inicjalizacja
taskfile --env dev run init

# 3. Synth + diff
taskfile --env dev run synth
taskfile --env dev run diff

# 4. Deploy
taskfile --env dev run deploy
taskfile --env prod run deploy

# 5. Destroy
taskfile --env dev run destroy
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run init` | Install CDK dependencies |
| `taskfile run synth` | Synthesize CloudFormation template |
| `taskfile run diff` | Show infrastructure diff |
| `taskfile run deploy` | Deploy CDK stack |
| `taskfile run destroy` | Destroy CDK stack |
| `taskfile run bootstrap` | Bootstrap CDK in AWS account |
| `taskfile run lint` | Lint TypeScript code |
| `taskfile run test` | Run CDK tests |
| `taskfile run list` | List all stacks |
| `taskfile run clean` | Remove cdk.out and node_modules |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: cdk-infra
description: "AWS CDK: multi-env infrastructure with TypeScript/Python"

variables:
  CDK_DIR: cdk
  CDK_APP: "npx ts-node bin/app.ts"

environments:
  dev:
    env_file: .env.dev
    variables:
      CDK_STACK: MyApp-Dev
      AWS_ACCOUNT: "123456789012"
      AWS_REGION: eu-west-1
      INSTANCE_SIZE: small

  staging:
    env_file: .env.staging
    variables:
      CDK_STACK: MyApp-Staging
      AWS_ACCOUNT: "123456789013"
      AWS_REGION: eu-west-1
      INSTANCE_SIZE: medium

  prod:
    env_file: .env.prod
    variables:
      CDK_STACK: MyApp-Prod
      AWS_ACCOUNT: "123456789014"
      AWS_REGION: eu-west-1
      INSTANCE_SIZE: large

tasks:

  init:
    desc: Install CDK dependencies
    dir: ${CDK_DIR}
    cmds:
      - npm install
      - npx cdk --version

  bootstrap:
    desc: Bootstrap CDK in AWS account
    dir: ${CDK_DIR}
    cmds:
      - npx cdk bootstrap aws://${AWS_ACCOUNT}/${AWS_REGION}

  synth:
    desc: Synthesize CloudFormation template
    dir: ${CDK_DIR}
    cmds:
      - npx cdk synth ${CDK_STACK} -c env=${INSTANCE_SIZE}

  diff:
    desc: Show infrastructure diff
    dir: ${CDK_DIR}
    cmds:
      - npx cdk diff ${CDK_STACK} -c env=${INSTANCE_SIZE}

  deploy:
    desc: Deploy CDK stack
    dir: ${CDK_DIR}
    deps: [synth]
    cmds:
      - npx cdk deploy ${CDK_STACK} -c env=${INSTANCE_SIZE} --require-approval never

  destroy:
    desc: Destroy CDK stack
    dir: ${CDK_DIR}
    cmds:
      - npx cdk destroy ${CDK_STACK} --force

  lint:
    desc: Lint TypeScript code
    dir: ${CDK_DIR}
    cmds:
      - npx eslint lib/ bin/
    ignore_errors: true

  test:
    desc: Run CDK tests
    dir: ${CDK_DIR}
    cmds:
      - npx jest

  list:
    desc: List all CDK stacks
    dir: ${CDK_DIR}
    cmds:
      - npx cdk list

  clean:
    desc: Remove cdk.out and node_modules
    dir: ${CDK_DIR}
    cmds:
      - rm -rf cdk.out node_modules
```

### cdk/package.json

```markpact:file path=cdk/package.json
{
  "name": "cdk-infra",
  "version": "1.0.0",
  "scripts": {
    "build": "tsc",
    "test": "jest",
    "cdk": "cdk"
  },
  "dependencies": {
    "aws-cdk-lib": "^2.100.0",
    "constructs": "^10.0.0"
  },
  "devDependencies": {
    "typescript": "^5.3.0",
    "ts-node": "^10.9.0",
    "jest": "^29.7.0",
    "ts-jest": "^29.1.0",
    "@types/jest": "^29.5.0",
    "aws-cdk": "^2.100.0"
  }
}
```

### .env.dev

```markpact:file path=.env.dev
AWS_PROFILE=dev
AWS_DEFAULT_REGION=eu-west-1
CDK_DEFAULT_ACCOUNT=123456789012
CDK_DEFAULT_REGION=eu-west-1
```

---

## 📚 Dokumentacja

- [AWS CDK Docs](https://docs.aws.amazon.com/cdk/)
- [CDK Workshop](https://cdkworkshop.com/)
- [CDK Patterns](https://cdkpatterns.com/)

**Licencja:** MIT
