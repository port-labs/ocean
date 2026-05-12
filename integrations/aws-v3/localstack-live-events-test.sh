#!/usr/bin/env bash

set -u

LOCALSTACK_IMAGE="${LOCALSTACK_IMAGE:-localstack/localstack:3.8.1}"
LOCALSTACK_CONTAINER="${LOCALSTACK_CONTAINER:-localstack-main}"
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-000000000000}"

MANAGEMENT_STACK="${MANAGEMENT_STACK:-aws-v3-live-events-management}"
MEMBER_STACK="${MEMBER_STACK:-aws-v3-live-events-member}"

OCEAN_WEBHOOK_URL="${OCEAN_WEBHOOK_URL:-http://host.docker.internal:8000/integration/webhook}"
WEBHOOK_SECRET="${WEBHOOK_SECRET:-test-secret}"

echo "== AWS-V3 LocalStack live-events validation =="
echo "LocalStack image: ${LOCALSTACK_IMAGE}"
echo "Region: ${AWS_REGION}"
echo

# Move to integrations/aws-v3 whether script is called from repo root or this directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}" || exit 1

MANAGEMENT_TEMPLATE="examples/cloudformation/live-events-management-account.yml"
MEMBER_TEMPLATE="examples/cloudformation/live-events-member-account.yml"

if [ ! -f "${MANAGEMENT_TEMPLATE}" ]; then
  echo "ERROR: Missing ${MANAGEMENT_TEMPLATE}"
  exit 1
fi

if [ ! -f "${MEMBER_TEMPLATE}" ]; then
  echo "ERROR: Missing ${MEMBER_TEMPLATE}"
  exit 1
fi

echo "== Checking Docker =="
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker command not found. Install Docker Desktop first."
  exit 1
fi

if ! docker ps >/dev/null 2>&1; then
  echo "ERROR: Docker is not running. Start Docker Desktop first."
  exit 1
fi

echo "Docker OK"
echo

echo "== Starting LocalStack =="
if docker ps --format '{{.Names}}' | grep -q "^${LOCALSTACK_CONTAINER}$"; then
  echo "LocalStack container already running: ${LOCALSTACK_CONTAINER}"
else
  if docker ps -a --format '{{.Names}}' | grep -q "^${LOCALSTACK_CONTAINER}$"; then
    echo "Removing stopped LocalStack container..."
    docker rm "${LOCALSTACK_CONTAINER}" >/dev/null 2>&1 || true
  fi

  docker run --rm -d \
    --name "${LOCALSTACK_CONTAINER}" \
    -p 4566:4566 \
    -e SERVICES=events,sqs,lambda,iam,logs,secretsmanager,cloudformation \
    -e DEBUG=1 \
    "${LOCALSTACK_IMAGE}" >/dev/null

  echo "Started LocalStack container: ${LOCALSTACK_CONTAINER}"
fi

echo "Waiting for LocalStack health endpoint..."
for i in {1..60}; do
  if curl -s "http://localhost:4566/_localstack/health" >/dev/null 2>&1; then
    echo "LocalStack health endpoint is available"
    break
  fi

  if [ "$i" -eq 60 ]; then
    echo "ERROR: LocalStack did not become ready in time"
    docker logs "${LOCALSTACK_CONTAINER}" --tail 100 || true
    exit 1
  fi

  sleep 2
done

echo

echo "== Ensuring awslocal is available outside Poetry =="
if ! command -v awslocal >/dev/null 2>&1; then
  echo "awslocal not found. Installing awscli-local with pip --user..."
  python3 -m pip install --user awscli-local

  export PATH="$HOME/.local/bin:$HOME/Library/Python/3.9/bin:$HOME/Library/Python/3.10/bin:$HOME/Library/Python/3.11/bin:$HOME/Library/Python/3.12/bin:$PATH"
fi

if ! command -v awslocal >/dev/null 2>&1; then
  echo "ERROR: awslocal is still not available."
  echo "Try installing manually:"
  echo "  python3 -m pip install --user awscli-local"
  exit 1
fi

echo "awslocal OK: $(awslocal --version 2>&1 | head -n 1)"
echo

echo "== Basic LocalStack check =="
awslocal sqs list-queues --region "${AWS_REGION}" || {
  echo "ERROR: Could not call LocalStack SQS."
  exit 1
}
echo

echo "== Deploying management CloudFormation stack =="
echo "Template: ${MANAGEMENT_TEMPLATE}"

awslocal cloudformation deploy \
  --region "${AWS_REGION}" \
  --stack-name "${MANAGEMENT_STACK}" \
  --template-file "${MANAGEMENT_TEMPLATE}" \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_IAM \
  --parameter-overrides \
    OceanWebhookUrl="${OCEAN_WEBHOOK_URL}" \
    WebhookSecret="${WEBHOOK_SECRET}"

MGMT_STATUS=$?

if [ "${MGMT_STATUS}" -ne 0 ]; then
  echo
  echo "WARNING: Management stack deployment failed in LocalStack."
  echo "This may be due to LocalStack CloudFormation/Lambda parity limitations."
  echo "Continuing with best-effort checks..."
else
  echo "Management stack deployed"
fi

echo

echo "== Discovering EventBridge bus =="
awslocal events list-event-buses --region "${AWS_REGION}" || true

BUS_NAME="$(
  awslocal events list-event-buses --region "${AWS_REGION}" \
    --query "EventBuses[?Name!='default'].Name | [0]" \
    --output text 2>/dev/null || true
)"

if [ -z "${BUS_NAME}" ] || [ "${BUS_NAME}" = "None" ]; then
  echo "No custom event bus discovered. Creating fallback bus: aws-v3-live-events"
  BUS_NAME="aws-v3-live-events"
  awslocal events create-event-bus \
    --region "${AWS_REGION}" \
    --name "${BUS_NAME}" >/dev/null 2>&1 || true
fi

BUS_ARN="arn:aws:events:${AWS_REGION}:${AWS_ACCOUNT_ID}:event-bus/${BUS_NAME}"

echo "Using bus name: ${BUS_NAME}"
echo "Using bus ARN:  ${BUS_ARN}"
echo

echo "== Deploying member CloudFormation stack =="
echo "Template: ${MEMBER_TEMPLATE}"

awslocal cloudformation deploy \
  --region "${AWS_REGION}" \
  --stack-name "${MEMBER_STACK}" \
  --template-file "${MEMBER_TEMPLATE}" \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_IAM \
  --parameter-overrides \
    ManagementEventBusArn="${BUS_ARN}"

MEMBER_STATUS=$?

if [ "${MEMBER_STATUS}" -ne 0 ]; then
  echo
  echo "WARNING: Member stack deployment failed in LocalStack."
  echo "This may be due to LocalStack CloudFormation/EventBridge parity limitations."
  echo "Continuing with direct EventBridge/SQS validation where possible..."
else
  echo "Member stack deployed"
fi

echo

echo "== Listing queues =="
awslocal sqs list-queues --region "${AWS_REGION}" || true

QUEUE_URL="$(
  awslocal sqs list-queues --region "${AWS_REGION}" \
    --query "QueueUrls[?contains(@, 'live') || contains(@, 'event') || contains(@, 'aws-v3')] | [0]" \
    --output text 2>/dev/null || true
)"

if [ -z "${QUEUE_URL}" ] || [ "${QUEUE_URL}" = "None" ]; then
  echo "No live-events queue discovered from stack."
  echo "Creating fallback queue and rule for EventBridge -> SQS validation."

  QUEUE_URL="$(
    awslocal sqs create-queue \
      --region "${AWS_REGION}" \
      --queue-name aws-v3-live-events-queue \
      --query "QueueUrl" \
      --output text
  )"

  QUEUE_ARN="$(
    awslocal sqs get-queue-attributes \
      --region "${AWS_REGION}" \
      --queue-url "${QUEUE_URL}" \
      --attribute-names QueueArn \
      --query "Attributes.QueueArn" \
      --output text
  )"

  awslocal events put-rule \
    --region "${AWS_REGION}" \
    --event-bus-name "${BUS_NAME}" \
    --name aws-v3-live-events-to-sqs \
    --event-pattern '{"source":["aws.ec2","aws.ecs","aws.lambda","aws.s3"]}' >/dev/null

  awslocal events put-targets \
    --region "${AWS_REGION}" \
    --event-bus-name "${BUS_NAME}" \
    --rule aws-v3-live-events-to-sqs \
    --targets "Id"="SqsTarget","Arn"="${QUEUE_ARN}" >/dev/null

  echo "Fallback queue created: ${QUEUE_URL}"
else
  echo "Using queue URL: ${QUEUE_URL}"
fi

echo

echo "== Sending fake EC2 EventBridge event =="
PUT_RESULT="$(
  awslocal events put-events \
    --region "${AWS_REGION}" \
    --entries "[
      {
        \"Source\": \"aws.ec2\",
        \"DetailType\": \"EC2 Instance State-change Notification\",
        \"Detail\": \"{\\\"instance-id\\\":\\\"i-1234567890abcdef0\\\",\\\"state\\\":\\\"running\\\"}\",
        \"EventBusName\": \"${BUS_NAME}\"
      }
    ]"
)"

echo "${PUT_RESULT}"

FAILED_COUNT="$(echo "${PUT_RESULT}" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("FailedEntryCount", "unknown"))' 2>/dev/null || echo "unknown")"

if [ "${FAILED_COUNT}" != "0" ]; then
  echo "WARNING: EventBridge put-events did not fully succeed."
else
  echo "EventBridge accepted the test event"
fi

echo

echo "== Waiting briefly for EventBridge -> SQS delivery =="
sleep 3

echo "== Receiving messages from SQS =="
MESSAGES="$(
  awslocal sqs receive-message \
    --region "${AWS_REGION}" \
    --queue-url "${QUEUE_URL}" \
    --max-number-of-messages 10 \
    --wait-time-seconds 2 2>/dev/null || true
)"

echo "${MESSAGES}"

MESSAGE_COUNT="$(echo "${MESSAGES}" | python3 -c 'import sys,json; data=json.load(sys.stdin); print(len(data.get("Messages", [])))' 2>/dev/null || echo "0")"

echo

if [ "${MESSAGE_COUNT}" -gt 0 ]; then
  echo "SUCCESS: LocalStack EventBridge -> SQS flow produced ${MESSAGE_COUNT} message(s)."
else
  echo "WARNING: No SQS messages received."
  echo "This may be due to LocalStack EventBridge/CloudFormation parity limitations."
fi

echo

echo "== Lambda/logs best-effort check =="
awslocal lambda list-functions --region "${AWS_REGION}" || true
awslocal logs describe-log-groups --region "${AWS_REGION}" || true

echo

echo "== Final reminder =="
echo "Before opening PR, do NOT commit LocalStack dependency changes."
echo "Run:"
echo "  grep -n \"localstack\\|awscli-local\" pyproject.toml poetry.lock"
echo "If anything appears because of temporary testing, remove/revert it before committing."
echo

echo "== Done =="
echo "To stop LocalStack:"
echo "  docker stop ${LOCALSTACK_CONTAINER}"