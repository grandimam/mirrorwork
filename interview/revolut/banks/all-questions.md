# Revolut — Complete Questions Bank

> All 193 unique questions extracted from 193 interview reports across [java_software_engineer.json](java_software_engineer.json), [revolut_senior_swe_interviews.json](revolut_senior_swe_interviews.json), [revolut_lead_swe_interviews.json](revolut_lead_swe_interviews.json), [revolut-backend-engineer-remote-nov-2021-120w.json](revolut-backend-engineer-remote-nov-2021-120w.json), and [swe.md](swe.md). Sorted by frequency within each section.

**Total raw mentions:** 264 | **Unique questions:** 193 | **Date range:** 2017-2026

## Contents
- [Live Coding Tasks](#live-coding-tasks) (46)
- [Concurrency & Threading](#concurrency--threading) (29)
- [Databases & Transactions](#databases--transactions) (27)
- [System Design](#system-design) (23)
- [Language Internals](#language-internals) (10)
- [Design Patterns & Principles](#design-patterns--principles) (12)
- [Algorithms & Data Structures](#algorithms--data-structures) (5)
- [Behavioral / HR Screening](#behavioral-/-hr-screening) (14)
- [Other Technical](#other-technical) (27)

## Live Coding Tasks

_46 unique questions._

- **×3** Circuit breaker coding task, databases, K8s
- **×2** Design a thread-safe service registry
- **×2** Design a URL shortener with TDD
- **×2** How would you handle concurrent requests in the load balancer?
- **×2** Implement a basic URL shortener service using TDD in Java
- **×2** Implement a load balancer registry that stores up to N server instances
- **×2** Implement a load balancer service in Core Java
- **×2** Implement a load balancer with register(), get() random and round-robin
- **×2** Implement a load balancer with TDD
- **×2** Implement a thread-safe load balancer in Java with register and get methods
- **×2** Implement a URL shortener using TDD step by step
- **×2** Implement account transfer service with thread safety
- **×2** Implement load balancer with round-robin and weighted strategies
- **×2** Implement URL shortener with TDD in Java
- **×2** Live code assessment: 3 tasks in a row on the same project about load balancing, focusing on code writing speed — JUnits required
- **×2** Look for the LoadBalancer exercise. It's always the same.
- a 3 (probably more) part question: 1. Implement a load balancer in Java that can register services 2. Add a random service selection algorithm 3. Add a round-robin selection algorithm everything should be tested.
- A classic question in the interview involves implementing either a Load Balancer or a URL Shortener class using a Test-Driven Development (TDD) approach. This means you are expected to write test cases first and then develop the working code that ensures all tests pass. The code must be production-ready, thread-safe (avoiding deadlocks), and should incorporate well-known design patterns such as Strategy. Additionally, you are required to implement functionality that involves probabilities (e.g., random selection) and ensure it is covered by test cases. It is also expected that you mention how probabilities can be tested using statistical methods, such as equal frequency distribution.
- Been asked about the cap theorem. Load Balancer.
- Build a registry of services focused on multithreading
- Caching, testing, concurrency, persistent storage
- Create a generator of SEO URLs — given a URL, make it SEO-friendly
- Create a load balancer with production quality considerations. Concurrency-focused task.
- Design a load balancer in Java — get and register methods
- Design a load balancer. Core Java, no Spring allowed. Transaction isolation levels.
- Design a LoadBalancerService with only a `registerServer()` method
- HashMap complexity, ACID, load balancer implementation
- Implement a simple load balancer in Java — 1 hour, no interim explanation needed, just coding
- Implement a thread-safe Account Ledger given a skeleton.
- Implement load balancer with in memory persistence
- Implement load balancer, concurrency, tests.
- Implement load balancer, url shortener. Implement money transfer method, make it thread safe and performant. Transaction isolation, optimistic/pessimistic locks, DB indexes, thread safety, stability/resilience patters, distirbuted transactions, event sourcing, DDD.
- Implement LoadBalancer using TDD style with Random/RoundRobin strategies.
- Implement money transfer method for java library.
- Implement simple load balancer with different balancing strategies
- Implement simple load-balancer with max of 10 instances and different load-balancing strategies support(round robin and random)
- Implement URL Shortener in Java
- Live coding + questions about complexity of the solution. Load balancer with some extra requirements added once implemented.
- Live coding — URL shortener
- Load balancer, register and retrieve instances.
- String interpolation to URI mapping
- Tech interview: account transfer + questions on DBs, Python and ops
- Working with random String generators.
- Write a simple load balancer, implement money transfer between two accounts function, design hotel booking system.
- Write API for money transfer
- Write code to generate a short URL

## Concurrency & Threading

_29 unique questions._

- **×3** Question about metics and traces Prometheus and Loki
- **×2** ACID properties, CAP theorem, Multithreading concepts, Sharding/Partitioning, DB indexes (pros and cons)
- **×2** Add thread safety to the registry
- **×2** Follow-up: add concurrency / thread-safety to the solution
- **×2** How does HashMap work internally under concurrent access?
- **×2** Java concurrency internals: locks, synchronized, volatile, thread pools
- **×2** Java concurrency questions: volatile, synchronized, happens-before
- **×2** Mainly core Java, Multithreading concepts, and distributed systems.
- **×2** Multithreading, partitioning, sharding, transaction isolation levels, db indexes, generally stuff from Designing Data-Intensive Applications book
- **×2** What is the difference between concurrency and parallelism?
- Can you write a code execution order?
- Concurrency issues and how to deal with them; Java core questions
- Deadlock; CAP theorem; URL generator
- Give me examples of concurrency problems. Give me one example of algorithm to store data in a database. What's the difference between sharding and replication?
- Have you worked with multithreads?
- How can we implement concurrency in Java?
- How to ensure thread safety in this method
- How to implement thread safety in round robin strategy
- How to prevent shared resources from being accessed by multiple threads simultaneously
- How would you guarantee thread safety / concurrent access to shared resources?
- Java concurrency breakdown, keywords and race conditions
- Java concurrency, multithreading, databases, transaction isolation
- Java, concurrency, databases, system design, performance optimizations etc. in other words there's a lot of ways to fail the interview. Not sure if the goal is to find out what you know or rather what you don't know.
- Lots of questions about concurrent and multithreaded programming, race conditions, deadlock, and optimization of relational databases.
- Mostly things about concurrency and DB isolation
- One of the questions was about concurrent collections and their usage.
- Technical Recruiter round: SOLID, CQRS, Concurrency challenges, Threads, SQL and NoSQL, DataStrucutres (Very basic)
- What is concurrency?
- Write some concurrent code. How could we implement this using Java concurrency mechanisms? Using database locking mechanisms?

## Databases & Transactions

_27 unique questions._

- **×2** ACID, CAP theorem, transaction isolation levels
- **×2** Explain ACID properties
- **×2** Explain transaction isolation levels in detail
- **×2** Questions about ACID, transaction isolation
- **×2** Too many theoretical questions related to database read and write
- **×2** What are DB indexes and when would you avoid them?
- **×2** What are the differences between optimistic and pessimistic locking?
- **×2** What are transaction isolation levels?
- **×2** What transaction isolation level you would use for online payment processing.
- ACID in SQL
- ACID principles. How to make a transaction in a database.
- ACID, Hashmaps, TDD live coding session.
- Are you familiar with ACID principles?
- Can elements be not equal if they have the same hashCode? What is the time complexity to get an element from a HashMap? What transaction levels exist in databases?
- Explain what is a transaction?
- Initial questions were basic like what is ACID, CQRS, equals and hashcode.
- Internal database data structures.
- Java fundamentals, distributed systems, databases, good coding and design practices
- List database transaction isolation levels.
- Python, SQL, and system design
- The 1st is a coding challenge. You are expecting to implement a hash map based solution. The 2nd is questions about threading, database locks, acid, sharding, etc. The 3rd is about system design. Mine was an ATM refill design.
- What are the different levels of isolation?
- What is a database transaction?
- What is ACID?
- What transaction isolation levels do you know? Describe them in detail.
- What's the best data structure to hold a database index?
- Write an SQL query with aggregation.

## System Design

_23 unique questions._

- **×2** Describe CAP theorem and give examples
- **×2** Design a distributed rate limiter
- **×2** Design a system for delivering physical cards to customers
- **×2** Pair programming: TDD — implement a simple system design as a single class
- **×2** System design / architecture discussion
- **×2** System design: design a notification service at scale
- **×2** System design: design a payment notification service
- **×2** Technical / System design interview with 4 Senior Engineers
- 2 pair programming sessions; System design
- Build a top-level design for a system responsible for temporary debit card issuance.
- CQRS (Command Query Responsibility Segregation).
- Create a system design of a hotel reservation system. Mobile app wants to book a room. To do it, you need to call 3rd party API which may not be reliable.
- Describe a given pattern in microservices architectures.
- Design a card-making service using a third-party provider
- Design a RESTful service about banking (requirements intentionally vague/abstract).
- Design a system which receives events from cache machines. Main focus on event sourcing, idempotency and CQRS.
- Multi-threading and system design
- SQL, Python, REST API, system design
- System Design an Apartment Booking application with a 3rd party API integration.
- System design card ordering feature
- System Design: be prepared for new tasks not shown on Glassdoor
- What is Cqrs, event sourcing
- Writing code, system architecture and design, distributed data systems

## Language Internals

_10 unique questions._

- ArraysList vs LinkedList and what structure can be used to achieve O(1) computation time to get/set data (HashMap)
- Do you have experience with hash maps?
- HashMap complexity
- How does the Hashmap work?
- If two objects have the same hash code, can they not be equal?
- The time complexity of a Python dictionary lookup
- What is new in Python 3?
- What is the complexity of operations in a HashMap?
- What's the computational cost of retrieving a key from a Python map?
- What's the time complexity of a lookup in a HashMap?

## Design Patterns & Principles

_12 unique questions._

- **×4** What are the SOLID principles?
- **×2** A lot of irrelevant questions: design patterns, DB questions, some are too theoretical and not applicable in real life
- **×2** Core Java TDD live coding challenge — implement a service with tests
- **×2** How would you apply design patterns to this solution?
- **×2** Implement a service step by step with evolving requirements (TDD style)
- **×2** Live coding — implement a service using TDD
- Code challenge regarding TDD, SOLID, Design Patterns and best OOP practices
- coding question on URL patterns
- Describe the OOP core principles
- Talk about the Memento pattern.
- TDD (Test-Driven Development).
- Which resilience design patterns are you aware of?

## Algorithms & Data Structures

_5 unique questions._

- **×2** General CS questions: data structures, time complexity
- Computational complexity of data structures.
- Duplicate character in a String; one C program, find the error
- Sorting algorithms, Binary Trees, Search Insert Position
- What is the worst case time complexity of quicksort?

## Behavioral / HR Screening

_14 unique questions._

- **×2** Why did you use a Set instead of a List here?
- Classic questions were asked. Why Revolut? What projects at your current job have challenged you?
- Difficulties in previous projects and how you overcame them
- Do you know about Revolut?
- Do you know the difference between x and y?
- From this list of technologies, which ones do you know?
- Have you worked without a framework?
- How many years of Java experience?
- Tell me about your current role. Why are you interested in this position?
- What do you know about Revolut?
- What's an example of when you displayed the idea of "Never settle"?
- What's your experience managing people?
- Why do you want to join?
- Why Revolut? What made you choose us?

## Other Technical

_27 unique questions._

- **×3** Available time for screening interview
- **×3** Standard questions that were mentioned several times here about multi-threading in Java
- **×3** There are some routine questions and some technical questions specific to the position
- **×2** Focus on clean code, tests, and incremental delivery
- **×2** Given a string, write a program that will output the string after a fixed URL
- **×2** Implement a service with simple business logic and incrementally evolving requirements
- **×2** Implement random and round-robin selection strategies
- **×2** Online technical interview — no feedback given
- **×2** Take-home technical assessment (no details provided)
- **×2** Take-home test task (extensive, multiple days of work)
- **×2** Write a Java solution for the given problem and write unit tests for it
- **×2** Write clean tests alongside each implementation step
- **×2** Write unit tests and refactor as requirements change
- "Simple" tech questions on screening interview
- Describe a project you delivered end-to-end in depth, focus on innovation and initiative.
- General questions related to SE
- How to use data analytics
- If the hash of two objects are equal, does that mean the two objects themselves are equal?
- Implement an algorithm with `get()` that randomly returns registered servers
- Implement another algorithm for RoundRobin
- Introductory interview — their technicals are much harder
- Most of the technical questions are already on GitHub (revolut_coding)
- Question about transfer between two accounts – how to achieve consistency and avoid double-spending money.
- Standard Software Engineer questions
- They were questions related to changes that the interviewer wanted on the project. I won't disclose them because it's not fair towards Revolut.
- Write an application based on abstract requirements.
- Write something based on abstract requirements.
