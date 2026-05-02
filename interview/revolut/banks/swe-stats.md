# Revolut — Interview Success Rate Analysis

## Referral vs. Non-Referral

| Channel           | Total | Accepted | Declined Offer | No Offer | Offer Rate | Acceptance Rate |
| ----------------- | ----- | -------- | -------------- | -------- | ---------- | --------------- |
| Employee Referral | 4     | 0        | 1              | 3        | 25%        | 0%              |
| Through Recruiter | 27    | 4        | 3              | 20       | 26%        | 15%             |
| Applied Online    | 25    | 2        | 3              | 20       | 20%        | 8%              |
| Other/Unknown     | 8     | 0        | 1              | 7        | 13%        | 0%              |

## Key Takeaways

- **Through recruiter** has the highest acceptance rate (15%) and offer rate (26%)
- **Employee referrals** have too small a sample (n=4) to draw conclusions — 1 got an offer but declined
- **Applied online** is the most common route but has a lower conversion rate (20% got an offer)
- Recruiter channel slightly edges out direct applications by ~6% in offer rate

## Interview Rounds

### Round 1 — Recruiter / HR Screening (20-45 min)

- Background, motivation, current role
- Basic technical questions (ACID, SOLID, HashMap complexity, OOP)
- "Why Revolut?" / "Why are you interested?"
- Technology familiarity checklist

### Round 2 — Online Assessment (optional, varies)

- HackerRank-style coding problems
- Take-home assignment (Python/SQL/REST API, 3 days to 1 week)
- Some candidates skip this round

### Round 3 — Live Coding (45-60 min)

- Done via Google Meet, IntelliJ allowed, no AI tools
- TDD expected — come prepared with a testing framework
- **Common tasks**:
  - **Load Balancer** — `registerServer()`, `get()` with random/round-robin, thread safety
  - **URL Shortener** — generate short URLs, retrieve by keyword
  - **Caching Service** — implement with concurrency handling
  - **Registry of Services** — multithreading focus

### Round 4 — Technical Interview (1 hour)

- Deep Java/Python knowledge, no Spring allowed
- Concurrency, multithreading, race conditions, deadlocks
- Database theory: ACID, transaction isolation levels, indexes
- Design patterns, distributed systems concepts
- Sometimes includes a second coding exercise

### Round 5 — System Design (1 hour)

- Architecture and distributed systems
- Not always included (sometimes reserved for senior-level)
- **Common tasks**:
  - Event sourcing system with idempotency and CQRS
  - Card-making service using a third-party provider
  - Money transfer API

### Round 6 — Team Fit / Culture (final)

- Collaboration and culture alignment
- Meeting with PO or manager of the target team
- Some candidates rejected at this stage despite passing technicals

## Questions Bank

### Recruiter / HR Round

- Tell me about your current role. Why are you interested in this position? — _#4_
- Do you know about Revolut? — _#3_
- What do you know about Revolut? — _#110_
- Why do you want to join? — _#102_
- Difficulties in previous projects and how you overcame them — _#6_
- What's an example of when you displayed "Never settle"? — _#107_
- From this list of technologies, which ones do you know? — _#90_
- How many years of Java experience? — _#79_
- Have you worked without a framework? — _#79_

### Concurrency & Multithreading

- How to prevent shared resources from being accessed by multiple threads simultaneously? — _#55_
- How would you guarantee thread safety / concurrent access to shared resources? — _#61_
- How to ensure thread safety in `registerServer()` method? — _#5_
- How to implement thread safety in a round robin strategy? — _#5_
- Have you worked with multithreads? — _#79_
- Can you write a code execution order? — _#68_
- What is concurrency? — _#83_

### Data Structures & Algorithms

- What is the complexity of operations in a HashMap? — _#73_
- What's the computational cost of retrieving a key from a Python map? — _#90_
- HashMap pessimistic time complexity when it degrades? — _#86_
- What is the worst case time complexity of quicksort? — _#108_
- What's the best data structure to hold a database index? — _#86, #90_
- Sorting algorithms, Binary Trees, Search Insert Position — _#54_
- If two objects have the same hash code, can they not be equal? — _#11_
- Duplicate character in a String — _#53_

### Databases

- What is ACID? — _#79, #83_
- What transaction isolation levels do you know? Describe them in detail. — _#76_
- What are the different levels of isolation? — _#21_
- ACID in SQL — _#83_
- Database indexes — _#76_

### Design & Architecture

- Which resilience design patterns are you aware of? — _#2_
- Describe the OOP core principles — _#99_
- What is new in Python 3? — _#108_
- CAP theorem — _#97_
- What is deadlock? — _#97_

### Live Coding Tasks

- Design a LoadBalancerService — `registerServer()`, `get()` with random and round-robin — _#5, #16, #36, #61, #71, #86_
- Implement a URL shortener with unit tests — _#1, #21, #87, #93_
- Build a registry of services focused on multithreading — _#46_
- Caching, testing, concurrency, persistent storage — _#51_
- String interpolation to URI mapping — _#52_
- Create a generator of SEO URLs — _#93_
- Write code to generate a short URL — _#87_
- Transfer money between bank accounts (pseudocode, concurrency focus) — _#76_

### System Design Tasks

- Design a system which receives events from cache machines (event sourcing, idempotency, CQRS) — _#26_
- Design a card-making service using a third-party provider — _#67_
- Write API for money transfer — _#117_
- How to use data analytics — _#56_

---

## Interview References

| #   | Date         | Outcome        | Sentiment | Difficulty | Location           |
| --- | ------------ | -------------- | --------- | ---------- | ------------------ |
| 1   | Mar 23, 2026 | No offer       | Neutral   | Difficult  | —                  |
| 2   | Mar 23, 2026 | Accepted offer | Positive  | Average    | Dubai              |
| 3   | Mar 15, 2026 | No offer       | Positive  | Average    | —                  |
| 4   | Mar 12, 2026 | No offer       | Positive  | Easy       | —                  |
| 5   | Feb 13, 2026 | No offer       | Negative  | Average    | Xique-Xique, Bahia |
| 6   | Jan 15, 2026 | Declined offer | Neutral   | Average    | Lisbon             |
| 11  | Nov 12, 2025 | No offer       | Positive  | Easy       | —                  |
| 16  | Sep 11, 2025 | No offer       | Neutral   | Difficult  | —                  |
| 21  | Jul 4, 2025  | No offer       | Neutral   | Difficult  | —                  |
| 26  | Mar 20, 2025 | No offer       | Negative  | Average    | Dubai              |
| 36  | Dec 7, 2024  | No offer       | Neutral   | Average    | Madrid             |
| 46  | Aug 6, 2024  | No offer       | Neutral   | Average    | —                  |
| 51  | Jun 13, 2024 | No offer       | Negative  | Easy       | —                  |
| 52  | Jun 6, 2024  | No offer       | Negative  | Easy       | —                  |
| 53  | May 28, 2024 | Declined offer | Positive  | Easy       | Chennai            |
| 54  | May 15, 2024 | Declined offer | Negative  | Difficult  | —                  |
| 55  | May 12, 2024 | No offer       | Neutral   | Average    | —                  |
| 56  | Apr 26, 2024 | Declined offer | Positive  | Difficult  | London             |
| 61  | Mar 9, 2024  | No offer       | Negative  | Difficult  | Portugal           |
| 67  | Oct 10, 2023 | No offer       | Negative  | Average    | —                  |
| 68  | Sep 30, 2023 | No offer       | Neutral   | Difficult  | Vilnius            |
| 71  | Jul 6, 2023  | No offer       | Positive  | Average    | Madrid             |
| 73  | Apr 28, 2023 | Declined offer | Positive  | Average    | Bucharest          |
| 76  | Mar 29, 2023 | Declined offer | Positive  | Average    | Warsaw             |
| 79  | Mar 15, 2023 | No offer       | Negative  | Difficult  | Brazil             |
| 83  | Jan 9, 2023  | No offer       | Negative  | Easy       | Athens             |
| 86  | Nov 22, 2022 | No offer       | Negative  | Easy       | —                  |
| 87  | Aug 8, 2022  | No offer       | Positive  | Average    | Barcelona          |
| 90  | Jun 9, 2022  | No offer       | Positive  | Easy       | Barcelona          |
| 93  | Feb 9, 2022  | No offer       | Negative  | Easy       | Barcelona          |
| 97  | Jun 16, 2021 | No offer       | Negative  | Easy       | —                  |
| 99  | Feb 4, 2021  | No offer       | Negative  | Average    | London             |
| 102 | Jan 21, 2021 | No offer       | Neutral   | Easy       | —                  |
| 107 | Jul 28, 2020 | Accepted offer | Neutral   | Easy       | London             |
| 108 | Apr 4, 2020  | No offer       | Positive  | Average    | —                  |
| 110 | Jan 18, 2020 | No offer       | Positive  | Easy       | —                  |
| 117 | Jun 21, 2019 | No offer       | Negative  | Average    | —                  |
