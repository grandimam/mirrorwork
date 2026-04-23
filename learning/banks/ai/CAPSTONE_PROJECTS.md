# Capstone Projects

## Project 1: Document Q&A System

**Objective:** Build a RAG-based Q&A system over a document collection.

**Components:**
- Document ingestion pipeline
- Chunking and embedding
- Vector storage (pgvector or Chroma)
- Retrieval with reranking
- Answer generation with citations

**Requirements:**
```python
# Core features
- Upload PDF/text documents
- Ask questions, get answers with sources
- Conversation history
- Streaming responses

# Production features
- Input/output guardrails
- Cost tracking
- Error handling
- Evaluation suite
```

**Skills Covered:** Modules 6, 7, 8, 17, 18, 19, 30

---

## Project 2: Customer Support Agent

**Objective:** Build an AI agent that handles customer support tickets.

**Components:**
- Intent classification
- Knowledge base retrieval
- Tool use (ticket lookup, order status, etc.)
- Human escalation
- Response generation

**Requirements:**
```python
# Core features
- Classify incoming requests
- Look up customer/order info via tools
- Generate helpful responses
- Escalate complex issues

# Production features
- Approval workflow for actions
- Audit logging
- Quality metrics
- Fallback handling
```

**Skills Covered:** Modules 5, 9, 10, 13, 15, 16, 26

---

## Project 3: Code Review Assistant

**Objective:** Build a tool that reviews pull requests and provides feedback.

**Components:**
- Git integration
- Code parsing and analysis
- Multi-file context handling
- Structured feedback generation

**Requirements:**
```python
# Core features
- Analyze PR diffs
- Identify bugs, style issues, improvements
- Generate inline comments
- Summarize overall feedback

# Production features
- GitHub/GitLab integration
- Configurable review rules
- Ignore patterns
- Batch review capability
```

**Skills Covered:** Modules 3, 4, 5, 19, 26

---

## Project 4: Multi-Agent Research System

**Objective:** Build a multi-agent system that researches topics and produces reports.

**Components:**
- Supervisor agent
- Research agents (web search, document analysis)
- Writing agent
- Review agent
- Coordination logic

**Requirements:**
```python
# Core features
- Accept research topics
- Coordinate multiple specialized agents
- Gather and synthesize information
- Produce structured reports

# Production features
- Progress tracking
- Source citation
- Iterative refinement
- Export formats (MD, PDF)
```

**Skills Covered:** Modules 9, 11, 14, 26

---

## Project 5: Voice-Enabled Assistant

**Objective:** Build a voice-activated AI assistant.

**Components:**
- Speech-to-text
- Intent handling
- Response generation
- Text-to-speech
- Conversation management

**Requirements:**
```python
# Core features
- Voice input/output
- Natural conversation flow
- Command handling
- Context retention

# Production features
- Wake word detection
- Noise handling
- Response streaming
- Latency optimization
```

**Skills Covered:** Modules 8, 25, 26, 28

---

## Project 6: Content Moderation Pipeline

**Objective:** Build a content moderation system for user-generated content.

**Components:**
- Multi-layer moderation
- Fast pattern matching
- LLM-based analysis
- Human review queue
- Analytics dashboard

**Requirements:**
```python
# Core features
- Screen text content
- Detect policy violations
- Flag for review
- Track decisions

# Production features
- Configurable rules
- Appeal handling
- Performance metrics
- Batch processing
```

**Skills Covered:** Modules 17, 29, 31

---

## Evaluation Criteria

For each project:

| Criterion | Description |
|-----------|-------------|
| Functionality | Core features work correctly |
| Code Quality | Clean, well-organized code |
| Error Handling | Graceful failure and recovery |
| Production Readiness | Logging, monitoring, guardrails |
| Documentation | Clear setup and usage instructions |
| Testing | Unit tests and evaluation suite |

---

## Getting Started

1. **Choose a project** based on your interests
2. **Plan the architecture** before coding
3. **Start simple** - get basic functionality working first
4. **Add production features** incrementally
5. **Test thoroughly** with diverse inputs
6. **Document** your decisions and learnings

**Tip:** Each project builds on multiple modules. Review the relevant modules before starting.
