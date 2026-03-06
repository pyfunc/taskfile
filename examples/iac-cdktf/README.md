# IaC CDK for Terraform (CDKTF) — Terraform with Programming Languages + Markpact

**Cały projekt CDKTF w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

CDK for Terraform — definiuj infrastrukturę Terraform w TypeScript/Python/Go/Java.
Łączy ekosystem providerów Terraform z programistycznym podejściem CDK,
multi-environment, zintegrowane z `taskfile`.

## Features covered

- **`dir`** — tasks run inside `cdktf/` directory
- **`env_file`** — per-environment cloud credentials
- **`deps`** — synth before deploy
- **CDKTF** — TypeScript/Python infrastructure
- **Terraform providers** — full ecosystem compatibility

## 🎯 Workflow

```bash
# 1. Wypakowanie projektu
markpact README.md && cd sandbox

# 2. Init
taskfile run init

# 3. Synth
taskfile --env dev run synth

# 4. Diff
taskfile --env dev run diff

# 5. Deploy
taskfile --env dev run deploy
taskfile --env prod run deploy

# 6. Destroy
taskfile --env dev run destroy
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run init` | Install CDKTF dependencies |
| `taskfile run synth` | Synthesize Terraform JSON |
| `taskfile run diff` | Preview changes |
| `taskfile run deploy` | Deploy infrastructure |
| `taskfile run destroy` | Destroy infrastructure |
| `taskfile run output` | Show outputs |
| `taskfile run providers` | Add/update providers |
| `taskfile run test` | Run CDKTF tests |
| `taskfile run lint` | Lint code |
| `taskfile run clean` | Remove cdktf.out directory |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: cdktf-infra
description: "CDK for Terraform: infrastructure with TypeScript/Python"

variables:
  CDKTF_DIR: cdktf
  STACK_NAME: my-stack

environments:
  dev:
    env_file: .env.dev
    variables:
      CDKTF_STACK: dev
      AWS_REGION: eu-west-1
      INSTANCE_TYPE: t3.small

  staging:
    env_file: .env.staging
    variables:
      CDKTF_STACK: staging
      AWS_REGION: eu-west-1
      INSTANCE_TYPE: t3.medium

  prod:
    env_file: .env.prod
    variables:
      CDKTF_STACK: prod
      AWS_REGION: eu-west-1
      INSTANCE_TYPE: t3.large

tasks:

  init:
    desc: Install CDKTF dependencies and generate providers
    dir: ${CDKTF_DIR}
    cmds:
      - npm install
      - cdktf get

  synth:
    desc: Synthesize Terraform JSON from CDKTF code
    dir: ${CDKTF_DIR}
    cmds:
      - cdktf synth --stack ${CDKTF_STACK}

  diff:
    desc: Preview infrastructure changes
    dir: ${CDKTF_DIR}
    cmds:
      - cdktf diff ${CDKTF_STACK}

  deploy:
    desc: Deploy infrastructure
    dir: ${CDKTF_DIR}
    deps: [synth]
    cmds:
      - cdktf deploy ${CDKTF_STACK} --auto-approve

  destroy:
    desc: Destroy infrastructure
    dir: ${CDKTF_DIR}
    cmds:
      - cdktf destroy ${CDKTF_STACK} --auto-approve

  output:
    desc: Show stack outputs
    dir: ${CDKTF_DIR}
    cmds:
      - cdktf output ${CDKTF_STACK}

  providers:
    desc: Add provider (use --var PROVIDER=aws)
    dir: ${CDKTF_DIR}
    cmds:
      - cdktf provider add ${PROVIDER}

  test:
    desc: Run CDKTF tests
    dir: ${CDKTF_DIR}
    cmds:
      - npx jest

  lint:
    desc: Lint TypeScript code
    dir: ${CDKTF_DIR}
    cmds:
      - npx eslint .
    ignore_errors: true

  clean:
    desc: Remove cdktf.out directory
    dir: ${CDKTF_DIR}
    cmds:
      - rm -rf cdktf.out/ node_modules/ .gen/
```

### cdktf/main.ts — CDKTF program (TypeScript)

```markpact:file path=cdktf/main.ts
import { Construct } from "constructs";
import { App, TerraformStack, TerraformOutput } from "cdktf";
import { AwsProvider } from "@cdktf/provider-aws/lib/provider";
import { Vpc } from "@cdktf/provider-aws/lib/vpc";
import { Subnet } from "@cdktf/provider-aws/lib/subnet";
import { SecurityGroup } from "@cdktf/provider-aws/lib/security-group";

class MyStack extends TerraformStack {
  constructor(scope: Construct, id: string) {
    super(scope, id);

    const region = process.env.AWS_REGION || "eu-west-1";

    new AwsProvider(this, "aws", { region });

    const vpc = new Vpc(this, "vpc", {
      cidrBlock: "10.0.0.0/16",
      enableDnsHostnames: true,
      tags: { Name: `${id}-vpc`, Environment: id, ManagedBy: "cdktf" },
    });

    const subnet = new Subnet(this, "subnet", {
      vpcId: vpc.id,
      cidrBlock: "10.0.1.0/24",
      mapPublicIpOnLaunch: true,
      tags: { Name: `${id}-subnet` },
    });

    new SecurityGroup(this, "sg", {
      vpcId: vpc.id,
      ingress: [
        { protocol: "tcp", fromPort: 80, toPort: 80, cidrBlocks: ["0.0.0.0/0"] },
        { protocol: "tcp", fromPort: 443, toPort: 443, cidrBlocks: ["0.0.0.0/0"] },
      ],
      egress: [
        { protocol: "-1", fromPort: 0, toPort: 0, cidrBlocks: ["0.0.0.0/0"] },
      ],
      tags: { Name: `${id}-sg` },
    });

    new TerraformOutput(this, "vpc_id", { value: vpc.id });
    new TerraformOutput(this, "subnet_id", { value: subnet.id });
  }
}

const app = new App();
new MyStack(app, "dev");
new MyStack(app, "staging");
new MyStack(app, "prod");
app.synth();
```

### cdktf/cdktf.json

```markpact:file path=cdktf/cdktf.json
{
  "language": "typescript",
  "app": "npx ts-node main.ts",
  "terraformProviders": ["aws@~>5.0"],
  "terraformModules": [],
  "codeMakerOutput": ".gen",
  "context": {}
}
```

### cdktf/package.json

```markpact:file path=cdktf/package.json
{
  "name": "cdktf-infra",
  "version": "1.0.0",
  "main": "main.ts",
  "scripts": {
    "build": "tsc",
    "synth": "cdktf synth",
    "test": "jest"
  },
  "dependencies": {
    "cdktf": "^0.20.0",
    "constructs": "^10.3.0",
    "@cdktf/provider-aws": "^19.0.0"
  },
  "devDependencies": {
    "typescript": "^5.3.0",
    "ts-node": "^10.9.0",
    "jest": "^29.7.0",
    "ts-jest": "^29.1.0",
    "@types/jest": "^29.5.0"
  }
}
```

### .env.dev

```markpact:file path=.env.dev
AWS_PROFILE=dev
AWS_DEFAULT_REGION=eu-west-1
```

---

## 📚 Dokumentacja

- [CDKTF Docs](https://developer.hashicorp.com/terraform/cdktf)
- [CDKTF Examples](https://github.com/hashicorp/terraform-cdk/tree/main/examples)
- [CDKTF Provider Registry](https://developer.hashicorp.com/terraform/cdktf/concepts/providers)

**Licencja:** MIT
