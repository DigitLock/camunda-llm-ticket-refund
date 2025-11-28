# Architecture Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Component Architecture](#component-architecture)
3. [External Task Pattern](#external-task-pattern)
4. [Communication Flow](#communication-flow)
5. [Error Handling Strategy](#error-handling-strategy)
6. [Security Considerations](#security-considerations)
7. [Deployment Architecture](#deployment-architecture)
8. [Performance Characteristics](#performance-characteristics)
9. [Scalability](#scalability)
10. [Monitoring & Observability](#monitoring--observability)

---

## System Overview

### High-Level Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                        User / API Client                         │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Camunda Platform 7.24.0                      │
│  ┌────────────────┐  ┌──────────────┐  ┌───────────────────┐   │
│  │  Process Engine│  │  REST API    │  │   Cockpit UI      │   │
│  │  (BPMN Runtime)│  │  (/engine-rest)│ │  (Monitoring)   │   │
│  └────────┬───────┘  └──────┬───────┘  └───────────────────┘   │
│           │                  │                                   │
│           └──────────────────┴──────────────┐                   │
│                                              ↓                   │
│                              ┌──────────────────────────┐        │
│                              │  H2 Database (embedded)  │        │
│                              │  Process instances       │        │
│                              │  History                 │        │
│                              │  Variables               │        │
│                              └──────────────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
                            ↑
                            │ REST API polling (10s interval)
                            │ Topic: analyze-fare-rules
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│              LLM Worker (Docker Container)                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  External Task Worker (Python 3.11)                      │   │
│  │  • Polls Camunda for External Tasks                      │   │
│  │  • Locks tasks (30s duration)                            │   │
│  │  • Processes business logic                              │   │
│  │  • Calls OpenAI API                                      │   │
│  │  • Returns results to Camunda                            │   │
│  └──────────────────────────┬───────────────────────────────┘   │
└─────────────────────────────┼───────────────────────────────────┘
                              │ HTTPS
                              ↓
                    ┌──────────────────────┐
                    │   OpenAI API         │
                    │   GPT-4o-mini model  │
                    │   Chat Completions   │
                    └──────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Technology |
|-----------|----------------|------------|
| **Camunda Platform** | Process orchestration, state management, persistence | Java, Tomcat, H2 |
| **BPMN Process** | Business logic definition, workflow routing | BPMN 2.0 XML |
| **LLM Worker** | External task processing, LLM integration | Python 3.11, Docker |
| **OpenAI API** | Fare rules analysis, decision making | GPT-4o-mini |
| **H2 Database** | Process state, history, variables storage | Embedded SQL database |

---

## Component Architecture

### Camunda Platform

**Version**: 7.24.0 Community Edition  
**Runtime**: Apache Tomcat 9  
**Database**: H2 (embedded, file-based)

**Key Features Used**:
- Process Engine API
- REST API (`/engine-rest`)
- External Task handling
- History service
- Cockpit (monitoring UI)
- Tasklist (user task interface)

**Configuration**:
```yaml
camunda:
  bpm:
    history-level: FULL
    history-time-to-live: 30 days
    job-execution:
      enabled: true
    external-tasks:
      default-retries: 3
      retry-time-cycle: PT5M
```

### LLM Worker

**Runtime**: Docker container  
**Base Image**: `python:3.11-slim`  
**Framework**: `camunda-external-task-client-python3`

**Architecture**:
```
┌─────────────────────────────────────────┐
│        LLM Worker Container              │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │  Main Process (llm_worker.py)     │ │
│  │                                    │ │
│  │  ┌──────────────────────────────┐ │ │
│  │  │  External Task Worker        │ │ │
│  │  │  • Subscribe to topics       │ │ │
│  │  │  • Poll Camunda (10s)        │ │ │
│  │  │  • Lock & fetch tasks        │ │ │
│  │  └──────────────────────────────┘ │ │
│  │                                    │ │
│  │  ┌──────────────────────────────┐ │ │
│  │  │  Task Handler                │ │ │
│  │  │  • Parse variables           │ │ │
│  │  │  • Build LLM prompt          │ │ │
│  │  │  • Call OpenAI API           │ │ │
│  │  │  • Return results            │ │ │
│  │  └──────────────────────────────┘ │ │
│  │                                    │ │
│  │  ┌──────────────────────────────┐ │ │
│  │  │  OpenAI Client               │ │ │
│  │  │  • API authentication        │ │ │
│  │  │  • Request formatting        │ │ │
│  │  │  • Response parsing          │ │ │
│  │  │  • Error handling            │ │ │
│  │  └──────────────────────────────┘ │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

**Worker Configuration**:
```python
worker = ExternalTaskWorker(
    worker_id="llm-fare-analyzer-1",
    base_url="http://localhost:8080/engine-rest",
    config={
        "maxTasks": 1,              # Process one task at a time
        "lockDuration": 30000,       # 30 seconds lock
        "asyncResponseTimeout": 10000, # 10s async timeout
    }
)
```

---

## External Task Pattern

### Pattern Overview

The External Task pattern decouples task execution from the process engine, enabling:
- Technology flexibility (Python, Node.js, Go, etc.)
- Independent scaling of workers
- Fault isolation
- Distributed processing

### How It Works
```
┌──────────────────────────────────────────────────────────────────┐
│                        SEQUENCE DIAGRAM                           │
└──────────────────────────────────────────────────────────────────┘

User                Camunda              Worker               OpenAI
  │                    │                   │                    │
  │ Start Process      │                   │                    │
  ├───────────────────>│                   │                    │
  │                    │                   │                    │
  │                    │ Create External   │                    │
  │                    │ Task (topic:      │                    │
  │                    │ analyze-fare-     │                    │
  │                    │ rules)            │                    │
  │                    │                   │                    │
  │                    │<──────────────────┤ Fetch & Lock       │
  │                    │    GET /external- │ (polling every 10s)│
  │                    │    task/fetchAnd- │                    │
  │                    │    Lock           │                    │
  │                    │                   │                    │
  │                    │ Task Details      │                    │
  │                    ├──────────────────>│                    │
  │                    │ (locked for 30s)  │                    │
  │                    │                   │                    │
  │                    │                   │ Process Task       │
  │                    │                   ├───────────────────>│
  │                    │                   │ POST /chat/        │
  │                    │                   │ completions        │
  │                    │                   │                    │
  │                    │                   │ GPT Response       │
  │                    │                   │<───────────────────┤
  │                    │                   │ {decision: "..."}  │
  │                    │                   │                    │
  │                    │<──────────────────┤ Complete Task      │
  │                    │ POST /external-   │ + variables        │
  │                    │ task/{id}/complete│                    │
  │                    │                   │                    │
  │                    │ Continue Process  │                    │
  │                    │ (use variables)   │                    │
  │                    │                   │                    │
```

### Task Lifecycle

1. **Task Creation**
   - Process engine reaches External Task activity
   - Creates task record in database
   - Status: CREATED

2. **Task Fetching & Locking**
   - Worker polls REST API: `GET /external-task/fetchAndLock`
   - Includes topic name: `analyze-fare-rules`
   - Camunda locks task for specified duration (30s)
   - Returns task details + process variables

3. **Task Processing**
   - Worker executes business logic
   - Calls external services (OpenAI API)
   - Builds result variables

4. **Task Completion**
   - Worker calls: `POST /external-task/{id}/complete`
   - Sends result variables back to Camunda
   - Task status: COMPLETED
   - Process continues to next activity

5. **Failure Handling**
   - If worker fails: task lock expires after 30s
   - Task becomes available for retry
   - If worker reports failure: `POST /external-task/{id}/failure`
   - Camunda can retry or escalate based on configuration

### BPMN Representation
```xml
<serviceTask id="task_check_fare_rules" name="Check fare rules">
  <extensionElements>
    <camunda:type>external</camunda:type>
    <camunda:topic>analyze-fare-rules</camunda:topic>
  </extensionElements>
</serviceTask>
```

### Advantages of External Task Pattern

| Aspect | Benefit |
|--------|---------|
| **Language Independence** | Workers can be written in any language with HTTP support |
| **Scalability** | Multiple worker instances can process tasks in parallel |
| **Fault Isolation** | Worker crash doesn't affect Camunda engine |
| **Deployment Flexibility** | Workers can be deployed independently |
| **Technology Stack** | Use best-fit technology for each task type |
| **Monitoring** | Separate metrics for engine and workers |

---

## Communication Flow

### Detailed Sequence: Full Refund Path with LLM
```
┌─────────┐   ┌─────────┐   ┌──────────┐   ┌─────────┐
│  User   │   │ Camunda │   │  Worker  │   │ OpenAI  │
└────┬────┘   └────┬────┘   └────┬─────┘   └────┬────┘
     │             │              │              │
     │ 1. POST /process-definition/key/ticket-refund/start
     ├────────────>│              │              │
     │             │              │              │
     │             │ 2. Create process instance │
     │             │    Execute: StartEvent     │
     │             │              │              │
     │             │ 3. Execute: Check fare rules (External Task)
     │             │    Create External Task    │
     │             │    Topic: analyze-fare-rules
     │             │              │              │
     │             │<─────────────┤ 4. GET /external-task/fetchAndLock
     │             │              │    {topic: "analyze-fare-rules"}
     │             │              │              │
     │             │ 5. Return task + variables │
     │             ├─────────────>│              │
     │             │ {             │              │
     │             │   id: "xxx",  │              │
     │             │   variables: {...}          │
     │             │ }             │              │
     │             │              │              │
     │             │              │ 6. Build prompt
     │             │              │    from variables
     │             │              │              │
     │             │              │ 7. POST /v1/chat/completions
     │             │              ├─────────────>│
     │             │              │ {            │
     │             │              │   model: "gpt-4o-mini",
     │             │              │   messages: [...]
     │             │              │ }            │
     │             │              │              │
     │             │              │ 8. Response  │
     │             │              │<─────────────┤
     │             │              │ {            │
     │             │              │   choices: [{
     │             │              │     message: {
     │             │              │       content: "ALLOWED"
     │             │              │     }         │
     │             │              │   }]          │
     │             │              │ }             │
     │             │              │              │
     │             │<─────────────┤ 9. POST /external-task/{id}/complete
     │             │              │    {         │
     │             │              │      variables: {
     │             │              │        fareRuleCheck: "ALLOWED",
     │             │              │        llmProvider: "OpenAI"
     │             │              │      }        │
     │             │              │    }          │
     │             │              │              │
     │             │ 10. Continue process        │
     │             │     Execute: Gateway        │
     │             │     Route: Full refund path │
     │             │              │              │
     │             │ 11. Execute: Calculate refund
     │             │              │              │
     │             │ 12. Execute: Process payment
     │             │              │              │
     │             │ 13. Execute: EndEvent       │
     │             │     Process COMPLETED       │
     │             │              │              │
```

### API Endpoints Used

**Camunda REST API**:
```
POST   /process-definition/key/{key}/start
GET    /external-task/fetchAndLock
POST   /external-task/{id}/complete
POST   /external-task/{id}/failure
GET    /history/process-instance
GET    /history/activity-instance
```

**OpenAI API**:
```
POST   https://api.openai.com/v1/chat/completions
```

### Data Flow

**Request to OpenAI**:
```json
{
  "model": "gpt-4o-mini",
  "messages": [
    {
      "role": "system",
      "content": "You are an airline policy expert. Respond with only one word."
    },
    {
      "role": "user",
      "content": "Analyze this ticket refund request:\n\nBooking ID: DEMO-xxx\nTicket Class: Economy\n..."
    }
  ],
  "max_tokens": 10,
  "temperature": 0.3
}
```

**Response from OpenAI**:
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1732737237,
  "model": "gpt-4o-mini-2024-07-18",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "WITH_PENALTY"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 148,
    "completion_tokens": 2,
    "total_tokens": 150
  }
}
```

**Variables Returned to Camunda**:
```json
{
  "fareRuleCheck": {
    "value": "WITH_PENALTY",
    "type": "String"
  },
  "llmProvider": {
    "value": "OpenAI GPT-4o-mini",
    "type": "String"
  },
  "llmReasoning": {
    "value": "AI analysis for DEMO-xxx",
    "type": "String"
  },
  "apiErrorCount": {
    "value": 0,
    "type": "Integer"
  }
}
```

---

## Error Handling Strategy

### 1. LLM Worker Errors

**Scenarios**:
- OpenAI API unavailable (network, rate limit, service outage)
- Invalid API key
- Timeout
- Unexpected response format

**Handling**:
```python
try:
    response = client.chat.completions.create(...)
    decision = response.choices[0].message.content.strip().upper()
    
    if decision not in ["ALLOWED", "WITH_PENALTY", "MANUAL"]:
        logger.warning(f"Invalid decision '{decision}', defaulting to MANUAL")
        decision = "MANUAL"
    
    return task.complete({
        "fareRuleCheck": decision,
        "llmProvider": "OpenAI GPT-4o-mini"
    })
    
except Exception as e:
    logger.error(f"OpenAI API Error: {e}")
    return task.complete({
        "fareRuleCheck": "MANUAL",
        "llmError": str(e)
    })
```

**Outcome**: Fallback to `MANUAL` review ensures process continues

### 2. Payment API Errors (Error Boundary Event)

**BPMN Implementation**:
```xml
<serviceTask id="task_process_payment" name="Process payment via gateway">
  <!-- Groovy script that throws BpmnError on failure -->
</serviceTask>

<boundaryEvent id="BoundaryEvent_PaymentError" 
               name="Payment API error" 
               attachedToRef="task_process_payment">
  <errorEventDefinition errorRef="PAYMENT_API_ERROR" />
</boundaryEvent>
```

**Flow**:
```
Process payment
  │
  ├─[SUCCESS]──────────────────> Continue to End
  │
  └─[ERROR]──> Error Boundary Event
               │
               └──> Log error & increment counter
                    │
                    └──> Gateway: Retry attempts < 3?
                         │
                         ├─[YES]──> Loop back to payment (retry)
                         │
                         └─[NO]───> Escalate to operator (User Task)
```

**Retry Logic**:
```groovy
def errorCount = execution.getVariable('apiErrorCount') ?: 0

if (errorCount < 2) {
    // Simulate failure for first 2 attempts
    throw new org.camunda.bpm.engine.delegate.BpmnError('PAYMENT_API_ERROR')
} else {
    // Success on 3rd attempt
    execution.setVariable('paymentStatus', 'SUCCESS')
}
```

**Gateway Conditions**:
- Retry path: `${apiErrorCount < 3}`
- Escalation path: `${apiErrorCount >= 3}`

### 3. SLA Violations (Timer Boundary Event)

**BPMN Implementation**:
```xml
<userTask id="task_manual_review" name="Manual review required">
  <extensionElements>
    <camunda:formData>
      <camunda:formField id="approved" type="boolean" label="Approve refund?" />
    </camunda:formData>
  </extensionElements>
</userTask>

<boundaryEvent id="BoundaryEvent_SLA" 
               name="2 hour SLA" 
               attachedToRef="task_manual_review"
               cancelActivity="true">
  <timerEventDefinition>
    <timeDuration>PT2H</timeDuration>
  </timerEventDefinition>
</boundaryEvent>
```

**Behavior**:
- **Interrupting Timer** (cancelActivity=true): Original task is canceled
- **Auto-escalation**: New task created for manager
- **Separate end event**: "SLA breach handled"

**Production vs Test Configuration**:
```
Production: PT2H (2 hours)
Testing: PT30S (30 seconds)
```

### 4. Task Lock Expiration

**Scenario**: Worker crashes while processing task

**Camunda Behavior**:
- Task locked for 30 seconds
- If no response within 30s, lock expires
- Task becomes available for other workers
- Prevents zombie tasks

**Worker Configuration**:
```python
config={
    "lockDuration": 30000,  # 30 seconds
    "asyncResponseTimeout": 10000  # 10 seconds
}
```

### 5. Invalid Process Variables

**Scenario**: Gateway condition evaluation fails due to missing variable

**Prevention**:
- Initialize all variables early in process
- Use default values: `execution.getVariable('var') ?: defaultValue`
- Validate variable types

**Example**:
```javascript
// Initialize at start
${execution.setVariable('apiErrorCount', 0)}

// Safe access with default
${execution.getVariable('approved') != null && execution.getVariable('approved') == true}
```

---

## Security Considerations

### Current Implementation (Development/Demo)

| Aspect | Implementation | Risk Level |
|--------|----------------|-----------|
| **API Keys** | Environment variable in Docker | ⚠️ Medium |
| **Camunda Auth** | None (Community Edition default) | ⚠️ High |
| **Network** | Docker host mode | ⚠️ Medium |
| **HTTPS** | No (local deployment) | ⚠️ Medium |
| **Secrets Management** | .env file | ⚠️ Medium |

### Production Recommendations

#### 1. Secrets Management
**Current**:
```bash
# .env file
OPENAI_API_KEY=sk-proj-xxxxx
```

**Production**:
```yaml
# Use HashiCorp Vault, AWS Secrets Manager, or Azure Key Vault
apiVersion: v1
kind: Secret
metadata:
  name: openai-credentials
type: Opaque
data:
  api-key: <base64-encoded-key>
```

#### 2. Camunda Authentication

**Enable Basic Auth**:
```yaml
# application.yaml
camunda:
  bpm:
    admin-user:
      id: admin
      password: ${ADMIN_PASSWORD}
    authorization:
      enabled: true
```

**Or OAuth2/LDAP**:
```yaml
spring:
  security:
    oauth2:
      client:
        registration:
          camunda:
            client-id: ${CLIENT_ID}
            client-secret: ${CLIENT_SECRET}
```

#### 3. Network Security

**Current**: Host network mode
```bash
docker run --network host ...
```

**Production**: Dedicated Docker network
```bash
docker network create camunda-net

docker run --network camunda-net \
  -e CAMUNDA_URL=http://camunda:8080/engine-rest \
  llm-worker
```

#### 4. API Rate Limiting

**Worker-side**:
```python
from ratelimit import limits, sleep_and_retry

@sleep_and_retry
@limits(calls=10, period=60)  # 10 calls per minute
def call_openai_api():
    return client.chat.completions.create(...)
```

#### 5. Input Validation

**Sanitize process variables**:
```python
def sanitize_input(booking_id: str) -> str:
    # Remove potential injection attacks
    return re.sub(r'[^\w\-]', '', booking_id)[:50]

booking_id = sanitize_input(task.get_variable("bookingId"))
```

#### 6. Audit Logging

**Log all LLM calls**:
```python
audit_logger.info({
    "event": "llm_call",
    "process_instance": process_instance_id,
    "input": sanitized_prompt,
    "output": decision,
    "cost": estimated_cost,
    "timestamp": datetime.utcnow()
})
```

---

## Deployment Architecture

### Development Setup (Current)
```
┌─────────────────────────────────────────────┐
│  Mac (Developer Machine)                    │
│  • Camunda Modeler 5.41.0                   │
│  • Git repository                           │
│  • BPMN file editing                        │
└─────────────────────────────────────────────┘
                    │
                    │ SSH, HTTP
                    ↓
┌─────────────────────────────────────────────┐
│  test-srv2 (192.168.13.52)                  │
│  Debian GNU/Linux 13+ (Testing/Unstable)    │
│  Kernel: 6.17.8, Python: 3.13               │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │  Docker: Camunda Platform           │   │
│  │  Port: 8080                          │   │
│  │  Image: camunda/camunda-bpm-platform│   │
│  │  Database: H2 (embedded)             │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │  Docker: LLM Worker                  │   │
│  │  Network: host                       │   │
│  │  Restart: unless-stopped             │   │
│  │  Environment: OPENAI_API_KEY         │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
                    │
                    │ HTTPS
                    ↓
           ┌─────────────────┐
           │  OpenAI API     │
           │  api.openai.com │
           └─────────────────┘
```

### Production Architecture (Recommended)
```
                        Internet
                            │
                            ↓
                   ┌─────────────────┐
                   │  Load Balancer  │
                   │  (HTTPS/TLS)    │
                   └────────┬────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         ↓                  ↓                  ↓
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Camunda Node 1  │ │ Camunda Node 2  │ │ Camunda Node 3  │
│ + Tasklist      │ │ + Tasklist      │ │ + Tasklist      │
│ + Cockpit       │ │ + Cockpit       │ │ + Cockpit       │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                             ↓
                   ┌──────────────────┐
                   │  PostgreSQL      │
                   │  (Clustered)     │
                   │  • Process state │
                   │  • History       │
                   │  • Variables     │
                   └──────────────────┘

┌────────────────────────────────────────────────────┐
│          LLM Worker Pool                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Worker 1 │  │ Worker 2 │  │ Worker 3 │  ...   │
│  └──────────┘  └──────────┘  └──────────┘        │
│  • Auto-scaling (HPA)                             │
│  • Load balanced by Camunda                       │
└────────────────────────────────────────────────────┘
                     │
                     ↓
            ┌─────────────────┐
            │  Redis          │
            │  • Task cache   │
            │  • Deduplication│
            └─────────────────┘
```

### Kubernetes Deployment (Example)
```yaml
# camunda-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: camunda-platform
spec:
  replicas: 3
  selector:
    matchLabels:
      app: camunda
  template:
    metadata:
      labels:
        app: camunda
    spec:
      containers:
      - name: camunda
        image: camunda/camunda-bpm-platform:7.24.0
        ports:
        - containerPort: 8080
        env:
        - name: DB_DRIVER
          value: org.postgresql.Driver
        - name: DB_URL
          value: jdbc:postgresql://postgres:5432/camunda
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"

---
# llm-worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-worker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: llm-worker
  template:
    metadata:
      labels:
        app: llm-worker
    spec:
      containers:
      - name: worker
        image: llm-worker:latest
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: openai-credentials
              key: api-key
        - name: CAMUNDA_URL
          value: http://camunda-platform:8080/engine-rest
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"

---
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: llm-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: llm-worker
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

---

## Performance Characteristics

### Measured Performance (Test Environment)

| Metric | Value | Notes |
|--------|-------|-------|
| **Process start time** | <10ms | From REST API call to first activity |
| **Service Task execution** | 0-25ms | In-process execution |
| **Gateway evaluation** | 0-1ms | Condition checking |
| **End Event** | 0ms | Instant |
| **User Task creation** | <50ms | Including form metadata |
| **LLM analysis** | 1-2s | OpenAI API call + processing |
| **External Task polling** | 10s interval | Configurable |
| **Task lock duration** | 30s | Prevents concurrent processing |

### End-to-End Timings

| Scenario | Duration | Breakdown |
|----------|----------|-----------|
| **Full Refund (Automated)** | 29ms | Start(0) + Check(25) + Gateway(1) + Calc(1) + Payment(1) + End(0) |
| **With Penalty (Automated)** | 12ms | Start(0) + Check(11) + Gateway(0) + Calc(0) + End(0) |
| **Manual Review** | 6-60s | Depends on human response time |
| **LLM-powered** | 1.5-2s | Worker processing + OpenAI API |
| **Error Retry (3x)** | 19ms | 3 attempts with boundary events |

### Throughput Estimates

**Single Worker**:
- LLM tasks: ~30-40 per minute (limited by OpenAI API)
- Automated tasks: ~1000+ per second (limited by Camunda engine)

**Scaled (10 workers)**:
- LLM tasks: ~300-400 per minute
- Bottleneck: OpenAI rate limits (3500 RPM on Tier 1)

### Resource Utilization

**Camunda Platform**:
```
CPU: 200-500m (idle to moderate load)
Memory: 1-2GB (H2 embedded database)
Disk: <100MB (process definitions + history)
```

**LLM Worker**:
```
CPU: 50-200m per worker
Memory: 256-512MB per worker
Network: ~10KB per LLM API call
```

---

## Scalability

### Horizontal Scaling Strategies

#### 1. Camunda Engine Clustering

**Requirements**:
- Shared database (PostgreSQL, Oracle, MySQL)
- Sticky sessions for Tasklist/Cockpit (if using UI)
- Job executor coordination

**Benefits**:
- High availability
- Load distribution
- Zero-downtime deployments

#### 2. Worker Pool Scaling

**Easy to scale** - stateless workers:
```bash
# Scale to 5 workers
docker-compose up --scale llm-worker=5
```

**Kubernetes HPA**:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: llm-worker-hpa
spec:
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        averageUtilization: 70
```

**Auto-scaling triggers**:
- CPU > 70%
- External task queue depth > 50
- API response time > 3s

### Bottlenecks & Mitigation

| Bottleneck | Impact | Mitigation |
|------------|--------|------------|
| **OpenAI Rate Limits** | 3500 RPM (Tier 1) | • Request rate increase from OpenAI<br>• Implement caching for repeated queries<br>• Use multiple API keys with load balancing |
| **Database I/O** | History writes | • Use PostgreSQL with optimized indexes<br>• Archive old history data<br>• Partition tables by date |
| **Network Latency** | Worker ↔ Camunda | • Deploy in same region/AZ<br>• Use persistent connections<br>• Batch operations where possible |
| **Task Locking** | Concurrent access | • Optimize lock duration (shorter for fast tasks)<br>• Increase worker count<br>• Use priority-based fetching |

### Caching Strategy

**Fare Rules Cache**:
```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=1000)
def analyze_fare_rules_cached(booking_hash: str):
    # Cache results for identical bookings
    return call_openai_api(booking_hash)

def process_task(task):
    # Create hash of booking details
    booking_data = f"{ticket_class}_{days_until_flight}_{purchase_date}"
    booking_hash = hashlib.md5(booking_data.encode()).hexdigest()
    
    return analyze_fare_rules_cached(booking_hash)
```

**Benefits**:
- Reduce API calls by 30-50%
- Faster response for repeated scenarios
- Lower costs

---

## Monitoring & Observability

### Key Metrics to Track

#### Process Metrics
```
camunda_process_instances_total{status="completed"}
camunda_process_instances_total{status="active"}
camunda_process_instance_duration_seconds
camunda_incidents_total
camunda_external_tasks_pending
```

#### Worker Metrics
```
llm_worker_tasks_processed_total
llm_worker_task_duration_seconds
llm_worker_openai_api_calls_total
llm_worker_openai_api_errors_total
llm_worker_openai_api_duration_seconds
llm_worker_cost_usd_total
```

#### Business Metrics
```
refund_requests_total{decision="ALLOWED"}
refund_requests_total{decision="WITH_PENALTY"}
refund_requests_total{decision="MANUAL"}
sla_breaches_total
manual_review_duration_seconds
```

### Prometheus Exporter Example
```python
from prometheus_client import Counter, Histogram, start_http_server

# Metrics
tasks_processed = Counter('llm_tasks_processed_total', 'Total tasks processed')
api_calls = Counter('openai_api_calls_total', 'Total OpenAI API calls')
api_duration = Histogram('openai_api_duration_seconds', 'OpenAI API call duration')
api_errors = Counter('openai_api_errors_total', 'OpenAI API errors')

def analyze_fare_rules(task):
    tasks_processed.inc()
    
    with api_duration.time():
        try:
            response = client.chat.completions.create(...)
            api_calls.inc()
            # ...
        except Exception as e:
            api_errors.inc()
            # ...

# Start metrics server on port 9090
start_http_server(9090)
```

### Grafana Dashboard

**Panels**:
1. **Process Throughput** - Instances started/completed per minute
2. **Active Instances** - Current running processes
3. **Task Queue Depth** - External tasks waiting
4. **LLM Response Time** - P50, P95, P99 latency
5. **Error Rate** - Failures per minute
6. **Cost Tracking** - OpenAI API spend over time
7. **SLA Compliance** - % of tasks completed within SLA

### Log Aggregation (ELK Stack)

**Structured Logging**:
```python
import structlog

log = structlog.get_logger()

log.info(
    "llm_task_completed",
    process_instance_id=process_id,
    booking_id=booking_id,
    decision=decision,
    duration_ms=duration,
    cost_usd=cost
)
```

**Elasticsearch Query**:
```json
{
  "query": {
    "bool": {
      "must": [
        {"match": {"event": "llm_task_completed"}},
        {"range": {"@timestamp": {"gte": "now-1h"}}}
      ]
    }
  },
  "aggs": {
    "avg_duration": {"avg": {"field": "duration_ms"}},
    "total_cost": {"sum": {"field": "cost_usd"}}
  }
}
```

### Alerting Rules

**Critical Alerts**:
```yaml
- alert: HighErrorRate
  expr: rate(llm_worker_openai_api_errors_total[5m]) > 0.1
  for: 5m
  annotations:
    summary: "High OpenAI API error rate"

- alert: TaskQueueBacklog
  expr: camunda_external_tasks_pending > 100
  for: 10m
  annotations:
    summary: "External task queue backing up"

- alert: SLABreachSpike
  expr: increase(sla_breaches_total[1h]) > 10
  annotations:
    summary: "Unusual number of SLA breaches"
```

---

## Conclusion

This architecture demonstrates:
- **Separation of Concerns**: Process orchestration, business logic, and AI inference are cleanly separated
- **Scalability**: Stateless workers enable horizontal scaling
- **Resilience**: Multiple error handling strategies ensure process continuity
- **Observability**: Comprehensive metrics and logging for production operations
- **Security**: Clear path from demo to production-hardened deployment

The External Task pattern proves ideal for LLM integration, providing flexibility, fault isolation, and independent scaling of AI workloads.

---

**Document Version**: 1.0  
**Last Updated**: November 28, 2025  
**Author**: Igor Kudinov
