# IaC CloudFormation — AWS Native Infrastructure + Markpact

**Cały projekt CloudFormation w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

AWS CloudFormation — natywne IaC dla AWS. Stack management z multi-environment
(dev/staging/prod), change sets, drift detection — zintegrowane z `taskfile`.

## Features covered

- **`env_file`** — per-environment AWS credentials
- **`condition`** — cfn-lint only if installed
- **`environment_groups`** — `all-prod` for rolling stack updates
- **`deps`** — validate before deploy
- **Change sets** — preview before apply

## 🎯 Workflow

```bash
# 1. Wypakowanie projektu
markpact README.md && cd sandbox

# 2. Walidacja
taskfile --env dev run validate

# 3. Deploy
taskfile --env dev run deploy
taskfile --env staging run deploy
taskfile --env prod run deploy

# 4. Status
taskfile --env prod run status
taskfile --env prod run outputs

# 5. Drift detection
taskfile --env prod run drift-detect

# 6. Destroy
taskfile --env dev run destroy
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run validate` | Validate CloudFormation templates |
| `taskfile run lint` | Lint templates (cfn-lint) |
| `taskfile run deploy` | Create/Update stack |
| `taskfile run changeset` | Create and review change set |
| `taskfile run status` | Show stack status |
| `taskfile run outputs` | Show stack outputs |
| `taskfile run events` | Show stack events |
| `taskfile run drift-detect` | Detect configuration drift |
| `taskfile run destroy` | Delete stack |
| `taskfile run cost` | Estimate monthly cost |
| `taskfile run clean` | Remove packaged templates |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: cfn-infra
description: "AWS CloudFormation: multi-env stack management, change sets, drift detection"

variables:
  TEMPLATE: templates/main.yaml
  STACK_PREFIX: myapp
  AWS_REGION: eu-west-1

environments:
  dev:
    env_file: .env.dev
    variables:
      STACK_NAME: ${STACK_PREFIX}-dev
      AWS_REGION: eu-west-1
      INSTANCE_TYPE: t3.small
      ENV_TAG: dev

  staging:
    env_file: .env.staging
    variables:
      STACK_NAME: ${STACK_PREFIX}-staging
      AWS_REGION: eu-west-1
      INSTANCE_TYPE: t3.medium
      ENV_TAG: staging

  prod:
    env_file: .env.prod
    variables:
      STACK_NAME: ${STACK_PREFIX}-prod
      AWS_REGION: eu-west-1
      INSTANCE_TYPE: t3.large
      ENV_TAG: prod

environment_groups:
  all-prod:
    members: [prod]
    strategy: rolling
    max_parallel: 1

tasks:

  validate:
    desc: Validate CloudFormation templates
    cmds:
      - aws cloudformation validate-template --template-body file://${TEMPLATE} --region ${AWS_REGION}

  lint:
    desc: Lint templates (cfn-lint)
    condition: "command -v cfn-lint >/dev/null 2>&1"
    cmds:
      - cfn-lint ${TEMPLATE}
      - cfn-lint templates/*.yaml
    ignore_errors: true

  deploy:
    desc: Create or update CloudFormation stack
    deps: [validate]
    cmds:
      - >-
        aws cloudformation deploy
        --template-file ${TEMPLATE}
        --stack-name ${STACK_NAME}
        --parameter-overrides
          Environment=${ENV_TAG}
          InstanceType=${INSTANCE_TYPE}
        --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM
        --region ${AWS_REGION}
        --tags Environment=${ENV_TAG} ManagedBy=taskfile

  changeset:
    desc: Create and describe change set before applying
    cmds:
      - >-
        aws cloudformation create-change-set
        --stack-name ${STACK_NAME}
        --template-body file://${TEMPLATE}
        --change-set-name taskfile-changeset
        --parameter-overrides
          ParameterKey=Environment,ParameterValue=${ENV_TAG}
          ParameterKey=InstanceType,ParameterValue=${INSTANCE_TYPE}
        --capabilities CAPABILITY_IAM
        --region ${AWS_REGION}
      - sleep 5
      - >-
        aws cloudformation describe-change-set
        --stack-name ${STACK_NAME}
        --change-set-name taskfile-changeset
        --region ${AWS_REGION}

  status:
    desc: Show stack status
    cmds:
      - aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${AWS_REGION} --query 'Stacks[0].StackStatus' --output text

  outputs:
    desc: Show stack outputs
    cmds:
      - aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${AWS_REGION} --query 'Stacks[0].Outputs' --output table

  events:
    desc: Show recent stack events
    cmds:
      - aws cloudformation describe-stack-events --stack-name ${STACK_NAME} --region ${AWS_REGION} --query 'StackEvents[:10]' --output table

  drift-detect:
    desc: Detect configuration drift
    cmds:
      - aws cloudformation detect-stack-drift --stack-name ${STACK_NAME} --region ${AWS_REGION}
      - sleep 10
      - aws cloudformation describe-stack-drift-detection-status --stack-name ${STACK_NAME} --region ${AWS_REGION}

  destroy:
    desc: Delete CloudFormation stack
    cmds:
      - aws cloudformation delete-stack --stack-name ${STACK_NAME} --region ${AWS_REGION}
      - aws cloudformation wait stack-delete-complete --stack-name ${STACK_NAME} --region ${AWS_REGION}

  cost:
    desc: Estimate monthly cost
    condition: "command -v infracost >/dev/null 2>&1"
    cmds:
      - infracost breakdown --path ${TEMPLATE}

  clean:
    desc: Remove packaged templates
    cmds:
      - rm -f packaged-*.yaml
      - rm -f packaged-*.json
```

### templates/main.yaml — CloudFormation template

```markpact:file path=templates/main.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Multi-environment web infrastructure

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, staging, prod]
  InstanceType:
    Type: String
    Default: t3.small

Resources:
  VPC:
    Type: AWS::EC2::VPC
    Properties:
      CidrBlock: 10.0.0.0/16
      EnableDnsHostnames: true
      Tags:
        - Key: Name
          Value: !Sub "${Environment}-vpc"
        - Key: Environment
          Value: !Ref Environment

  PublicSubnet:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref VPC
      CidrBlock: 10.0.1.0/24
      MapPublicIpOnLaunch: true
      Tags:
        - Key: Name
          Value: !Sub "${Environment}-public-subnet"

  SecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: !Sub "${Environment} web security group"
      VpcId: !Ref VPC
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 80
          ToPort: 80
          CidrIp: 0.0.0.0/0
        - IpProtocol: tcp
          FromPort: 443
          ToPort: 443
          CidrIp: 0.0.0.0/0

Outputs:
  VpcId:
    Value: !Ref VPC
    Export:
      Name: !Sub "${Environment}-VpcId"
  SubnetId:
    Value: !Ref PublicSubnet
    Export:
      Name: !Sub "${Environment}-SubnetId"
```

### .env.dev

```markpact:file path=.env.dev
AWS_PROFILE=dev
AWS_DEFAULT_REGION=eu-west-1
```

---

## 📚 Dokumentacja

- [AWS CloudFormation Docs](https://docs.aws.amazon.com/cloudformation/)
- [cfn-lint](https://github.com/aws-cloudformation/cfn-lint)
- [CloudFormation Best Practices](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/best-practices.html)

**Licencja:** MIT
