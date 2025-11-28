# Camunda LLM Ticket Refund - Automated BPMN Process

Automated airline ticket refund processing with AI-powered decision making using OpenAI GPT-4o-mini and Camunda Platform.

## 🎯 Project Overview

This project demonstrates a production-ready BPMN process for handling airline ticket refund requests with intelligent automation. Built as a portfolio project showcasing Business Analyst skills, BPMN expertise, and LLM integration capabilities.

**Business Context**: Travel technology solution for airline companies to automate refund processing, reduce manual workload, and improve customer experience through intelligent decision-making.

## 🏗 Architecture

- **Process Engine**: Camunda Platform 7.24.0
- **LLM Integration**: OpenAI GPT-4o-mini via External Task Worker
- **Worker Runtime**: Python 3.11 in Docker container
- **Deployment**: Production-ready setup with error handling and monitoring

## ✨ Features

### BPMN Elements Implemented
- ✅ Service Tasks (automated processing)
- ✅ User Tasks (manual review with forms)
- ✅ Exclusive Gateways (business logic routing)
- ✅ Error Boundary Events (retry mechanism with 3 attempts)
- ✅ Timer Boundary Events (SLA monitoring with auto-escalation)
- ✅ External Tasks (LLM integration point)
- ✅ Process Variables (state management)
- ✅ Multiple End Events (different process outcomes)

### Business Scenarios Covered
1. **Full Refund** - Fully automated approval path
2. **Refund with Penalty** - Automatic fee calculation
3. **Manual Review - Approved** - Human decision required (complex cases)
4. **Manual Review - Rejected** - Human rejection with reasoning
5. **SLA Breach** - Automatic escalation after 2-hour timeout
6. **Error Handling** - Payment API failure with retry loop

## 🔍 Camunda History Viewer (Companion Tool)

**Challenge**: Camunda Community Edition lacks a built-in UI for viewing historical process instances.

**Solution**: Developed a separate React-based history viewer tool.

**[→ Camunda History Viewer Repository](https://github.com/DigitLock/camunda-history-viewer)**

**Features**:
- 📊 Visual timeline of completed process instances
- 🔍 Activity-by-activity execution history
- 📝 Process variables inspection
- 🎨 Clean, intuitive React UI
- 🔌 Direct REST API integration with Camunda

This companion project demonstrates:
- Problem-solving approach to platform limitations
- Full-stack development skills (React + REST API)
- Understanding of Camunda architecture and API

**Used extensively during testing** to analyze all 6 test scenarios documented below.

## 🤖 AI Integration Details

### How LLM Analyzes Refund Requests

The External Task Worker uses GPT-4o-mini to analyze:
- Ticket class (Economy, Business, First)
- Purchase date vs Flight date
- Days until departure
- Airline refund policies

**LLM Decision Categories**:
- `ALLOWED` - Full refund with no penalty
- `WITH_PENALTY` - Refund possible but with cancellation fee
- `MANUAL` - Requires human review (edge cases)

**Performance**:
- Response time: ~1-2 seconds per request
- Cost: ~$0.0001 per analysis
- Fallback: Manual review on API errors

## 🚀 Quick Start

### Prerequisites
- Docker installed
- Camunda Platform 7.x running
- OpenAI API key ([get one here](https://platform.openai.com/api-keys))
- *Optional*: [Camunda History Viewer](https://github.com/DigitLock/camunda-history-viewer) for viewing completed processes

### Installation

1. **Clone repository**:
```bash
git clone https://github.com/DigitLock/camunda-llm-ticket-refund.git
cd camunda-llm-ticket-refund
```

2. **Configure OpenAI API key**:
```bash
cd workers/llm-worker
cp .env.example .env
nano .env  # Add your API key: OPENAI_API_KEY=sk-proj-...
```

3. **Start LLM Worker**:
```bash
cd ../../scripts
./start-worker.sh
```

4. **Deploy BPMN process to Camunda**:
```bash
./deploy.sh
```

5. **Trigger process** via Camunda Cockpit or REST API

### Manual Deployment (Alternative)

If scripts don't work, deploy manually:

1. Start worker:
```bash
cd workers/llm-worker
docker build -t llm-worker:latest .
docker run -d --name llm-worker --network host --env-file .env llm-worker:latest
```

2. Deploy BPMN via Camunda Modeler:
   - Open `bpmn/ticket-refund-process.bpmn`
   - Deploy to your Camunda instance

## 📊 Test Results

All 6 scenarios tested and verified on Camunda Platform 7.24.0:

| # | Scenario | Elements Used | Duration | Status |
|---|----------|---------------|----------|--------|
| 1 | Full Refund (Happy Path) | Service Tasks, Gateway | 29ms | ✅ PASS |
| 2 | Refund with Penalty | Service Tasks, Gateway | 12ms | ✅ PASS |
| 3 | Manual Review - Approved | User Task, Form, Gateway | 58.4s | ✅ PASS |
| 4 | Manual Review - Rejected | User Task, Form, Gateway | 6.2s | ✅ PASS |
| 5 | SLA Breach Timer | Timer Boundary Event (30s) | 130.5s | ✅ PASS |
| 6 | Error Handling Retry | Error Boundary Event, Loop | 19ms | ✅ PASS |

**Total API Calls During Testing**: 15 requests  
**Total Cost**: ~$0.002 USD  
**Success Rate**: 100%

## 📁 Project Structure
```
camunda-llm-ticket-refund/
├── README.md                      # This file
├── .gitignore                     # Git exclusions
├── bpmn/
│   └── ticket-refund-process.bpmn # BPMN 2.0 process definition
├── workers/
│   └── llm-worker/
│       ├── llm_worker.py          # External Task Worker
│       ├── requirements.txt       # Python dependencies
│       ├── Dockerfile             # Container definition
│       └── .env.example           # Environment template
├── docs/
│   └── diagram.png                # Process diagram screenshot
└── scripts/
    ├── deploy.sh                  # Deploy process to Camunda
    └── start-worker.sh            # Start worker container
```

## 🛠 Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Process Engine | Camunda Platform Community Edition | 7.24.0 |
| Modeling | BPMN 2.0 | - |
| LLM Provider | OpenAI | GPT-4o-mini |
| Worker Language | Python | 3.11 |
| Worker Framework | camunda-external-task-client-python3 | 4.3.0 |
| Containerization | Docker | Latest |
| API Client | openai-python | 1.54.4 |

## 🎓 Learning Outcomes

This project demonstrates:
- **Business Analysis**: Process decomposition, edge case identification
- **BPMN Expertise**: Advanced patterns (boundary events, external tasks)
- **Integration Skills**: REST API, External Task pattern
- **AI/LLM Integration**: Practical application of LLMs in business processes
- **DevOps**: Dockerization, production deployment patterns
- **Problem Solving**: Developed companion tool to overcome platform limitations

## 🔮 Future Enhancements

Potential improvements for production use:
- [ ] Add authentication/authorization
- [ ] Implement caching for repeated fare rule queries
- [ ] Add metrics and monitoring (Prometheus/Grafana)
- [ ] Support multiple LLM providers (Claude, Gemini)
- [ ] Add unit tests for worker logic
- [ ] Implement circuit breaker pattern for API calls

## 📝 License

MIT License - feel free to use for learning and portfolio purposes.

## 👤 Author

**Igor Kudinov**  
Senior Business Systems Analyst

- 15+ years experience in banking, fintech, and cryptocurrency industries
- Expertise: System migrations, API documentation, BPMN, compliance (AML, Travel Rule)
- Portfolio project demonstrating BPMN modeling and LLM integration

## 🤝 Contributing

This is a portfolio/demonstration project. Feedback and suggestions are welcome via issues.

---

**Note**: This is a demonstration project showcasing technical skills. For production deployment, additional security hardening, monitoring, and testing should be implemented.
