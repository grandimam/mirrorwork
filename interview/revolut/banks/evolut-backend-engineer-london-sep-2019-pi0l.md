# Revolut | Backend Engineer | London | Sep 2019 — Interview Experience (Result: Rejected)

> **Source:** LeetCode Discuss — Anonymous User | Posted: May 25, 2020 | Views: 3,631

---

## Candidate Profile

| Field                     | Details            |
| ------------------------- | ------------------ |
| Years of Experience       | 12 YOE             |
| Position Applied For      | Backend Engineer   |
| Candidate's Current Level | Principal Engineer |
| Role Location             | London, UK         |
| Candidate's Base          | Bangalore, India   |
| Interview Date            | September 2019     |
| Outcome                   | ❌ Rejected        |

---

## Preparation

> Very generic preparation: **Cracking the Coding Interview (CTCI)** + a few LeetCode questions + theory topics.

---

## How It Started

The recruiter reached out on **LinkedIn** for the Backend Engineer role at Revolut, London. The candidate was aware of Revolut's reputation for work-life balance issues but was drawn in by curiosity about the process and the appeal of London. They decided to proceed.

---

## Interview Process Overview

| Step   | Type                        | Format                  |
| ------ | --------------------------- | ----------------------- |
| Step 1 | Take-Home Assignment        | 1-week coding task      |
| Step 2 | Online Technical Discussion | Live multi-part session |

---

## Step 1: Take-Home Assignment

### Task

> Design and implement a **RESTful API** (including data model and the backing implementation) for **money transfers between accounts**.

### Constraints

- Any framework could be used **except Spring**
- Code must be **workable** and **testable**
- Must include **proper unit tests (UT)**

### Timeline

- Candidate given **1 week** to submit
- Revolut took **1 week** to review

---

## Step 2: Online Technical Discussion

### Part A — Solution Review

- Discuss the take-home assignment solution
- Walk through various design choices made

### Part B — Current Project Deep-Dive

- Explain current project architecture
- Explain current project design decisions

### Part C — Theory Questions

**Broad topics covered:**
`RDBMS` · `Data Structures` · `Algorithms` · `CI/CD` · `Docker` · `Transactions` · `Isolation` · `Deadlock` · `Pessimistic Locking` · `Consistency` · `Indexing` · `Garbage Collection` · `HashMap` · `HashCode`

**Specific questions asked:**

1. **What is a root object in garbage collection?**
2. **What are the different isolation levels in RDBMS?**
3. **How do you set up a slow query log in RDBMS?**

---

### Part D — Peer Programming (Live Coding in IDE)

**Language insisted upon by interviewers: Java**
_(the candidate had never worked in Java professionally)_

**Problem:** Write a frequency counter

- Count the frequency of elements in a collection

**Follow-up constraints added progressively:**

- _What if the data won't fit in memory?_ → Think: streaming / external memory / disk-based approaches
- _What if the function is called by many threads simultaneously?_ → Think: thread safety, concurrency, locks, ConcurrentHashMap

---

### Part E — Candidate Q&A

- Candidate was given **10 minutes** at the end to ask the interviewers questions

---

## Outcome & Feedback

One week after the technical discussion, the recruiter delivered a rejection with the following feedback:

| Area                    | Verdict                                                                                |
| ----------------------- | -------------------------------------------------------------------------------------- |
| Take-home assignment    | ✅ Strong                                                                              |
| Theory knowledge        | ✅ Strong                                                                              |
| Peer programming (Java) | ❌ Weak — candidate had never used Java professionally but interviewers insisted on it |

---

## Candidate's Takeaways

- **Java dominance:** Java has too strong a pull in the industry — candidate decided to polish it via LeetCode
- **Morale boost:** Despite the rejection, completing the assignment well and covering most of the theory was encouraging
- **Reignited interest:** This experience reignited the candidate's motivation to keep interviewing

---

## Key Topics to Study (Derived from This Interview)

### 🗄️ Databases / RDBMS

- **Isolation levels:** Read Uncommitted → Read Committed → Repeatable Read → Serializable
- Transactions, consistency, and the ACID properties
- Deadlock: causes, detection, prevention
- Pessimistic vs. optimistic locking
- What an index is and when/how to use it in production
- How to configure and interpret a **slow query log**

### ⚙️ Systems / DevOps

- CI/CD pipeline concepts
- Docker fundamentals (containers, images, volumes)

### ☕ Java / JVM

- **Garbage collection** — what a "GC root" is (stack references, static fields, JNI references)
- **HashMap internals** — hashCode(), equals(), collision handling, load factor
- Thread-safe alternatives: `ConcurrentHashMap`, `synchronized`, `ReentrantLock`

### 📊 Data Structures & Algorithms

- Frequency counter pattern
- Handling data too large for memory: streaming, chunking, external sort, disk-based maps
- Concurrency patterns for shared data structures

### 🌐 System Design / API Design

- RESTful API design principles (resources, HTTP verbs, status codes)
- Data modeling for financial systems (accounts, balances, transfers, idempotency)
- Structuring a project for testability: unit tests, separation of concerns, dependency injection

---

## Comment on the Post

**yaguar** _(Aug 01, 2022)_:

> "Hi, would you mind telling what was your prior experience and where were you applying it from?"

_No reply was recorded._

---

_Captured from LeetCode Discuss — https://leetcode.com/discuss/post/651695/revolut-backend-engineer-london-sep-2019-pi0l/_
