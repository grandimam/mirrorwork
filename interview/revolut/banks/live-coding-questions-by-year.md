# Revolut — Live Coding Questions by Year

> **80** raw mentions of live-coding tasks across 58 unique question texts, extracted from interview reports spanning **2019–2026**. Filtered by keyword match (Load Balancer, URL Shortener, Money Transfer, TDD live coding, etc.) — see [all-questions.md](all-questions.md) for the full bank.

## Year summary

| Year | Unique questions | Raw mentions |
|------|-----------------:|-------------:|
| 2026 | 4 | 4 |
| 2025 | 16 | 22 |
| 2024 | 20 | 28 |
| 2023 | 4 | 6 |
| 2022 | 4 | 4 |
| 2021 | 5 | 9 |
| 2020 | 3 | 4 |
| 2019 | 2 | 3 |

## 2026

- Design a LoadBalancerService with only a `registerServer()` method
- Implement money transfer method for java library.
- Live coding — URL shortener
- Tech interview: account transfer + questions on DBs, Python and ops

## 2025

- Circuit breaker coding task, databases, K8s (×3)
- Design a URL shortener with TDD (×2)
- How would you handle concurrent requests in the load balancer? (×2)
- Implement a thread-safe load balancer in Java with register and get methods (×2)
- Implement a URL shortener using TDD step by step (×2)
- A classic question in the interview involves implementing either a Load Balancer or a URL Shortener class using a Test-Driven Development (TDD) approach. This means you are expected to write test cases first and then develop the working code that ensures all tests pass. The code must be production-ready, thread-safe (avoiding deadlocks), and should incorporate well-known design patterns such as Strategy. Additionally, you are required to implement functionality that involves probabilities (e.g., random selection) and ensure it is covered by test cases. It is also expected that you mention how probabilities can be tested using statistical methods, such as equal frequency distribution.
- Code challenge regarding TDD, SOLID, Design Patterns and best OOP practices
- Create a load balancer with production quality considerations. Concurrency-focused task.
- Design a load balancer in Java — get and register methods
- Implement a thread-safe Account Ledger given a skeleton.
- Implement load balancer, url shortener. Implement money transfer method, make it thread safe and performant. Transaction isolation, optimistic/pessimistic locks, DB indexes, thread safety, stability/resilience patters, distirbuted transactions, event sourcing, DDD.
- Implement LoadBalancer using TDD style with Random/RoundRobin strategies.
- Implement simple load balancer with different balancing strategies
- Live coding + questions about complexity of the solution. Load balancer with some extra requirements added once implemented.
- System Design an Apartment Booking application with a 3rd party API integration.
- Write a simple load balancer, implement money transfer between two accounts function, design hotel booking system.

## 2024

- Core Java TDD live coding challenge — implement a service with tests (×2)
- Design a thread-safe service registry (×2)
- Implement a basic URL shortener service using TDD in Java (×2)
- Implement a load balancer registry that stores up to N server instances (×2)
- Implement a load balancer service in Core Java (×2)
- Implement load balancer with round-robin and weighted strategies (×2)
- Live coding — implement a service using TDD (×2)
- Look for the LoadBalancer exercise. It's always the same. (×2)
- a 3 (probably more) part question: 1. Implement a load balancer in Java that can register services 2. Add a random service selection algorithm 3. Add a round-robin selection algorithm everything should be tested.
- ACID, Hashmaps, TDD live coding session.
- Been asked about the cap theorem. Load Balancer.
- Build a registry of services focused on multithreading
- Caching, testing, concurrency, persistent storage
- Implement a simple load balancer in Java — 1 hour, no interim explanation needed, just coding
- Implement load balancer with in memory persistence
- Implement load balancer, concurrency, tests.
- Implement simple load-balancer with max of 10 instances and different load-balancing strategies support(round robin and random)
- Implement URL Shortener in Java
- Load balancer, register and retrieve instances.
- String interpolation to URI mapping

## 2023

- Implement a load balancer with register(), get() random and round-robin (×2)
- Implement URL shortener with TDD in Java (×2)
- Design a load balancer. Core Java, no Spring allowed. Transaction isolation levels.
- Question about transfer between two accounts – how to achieve consistency and avoid double-spending money.

## 2022

- 2 pair programming sessions; System design
- Create a generator of SEO URLs — given a URL, make it SEO-friendly
- HashMap complexity, ACID, load balancer implementation
- Write code to generate a short URL

## 2021

- Given a string, write a program that will output the string after a fixed URL (×2)
- Implement a load balancer with TDD (×2)
- Implement a service step by step with evolving requirements (TDD style) (×2)
- Implement account transfer service with thread safety (×2)
- Write some concurrent code. How could we implement this using Java concurrency mechanisms? Using database locking mechanisms?

## 2020

- Live code assessment: 3 tasks in a row on the same project about load balancing, focusing on code writing speed — JUnits required (×2)
- TDD (Test-Driven Development).
- Working with random String generators.

## 2019

- Pair programming: TDD — implement a simple system design as a single class (×2)
- Write API for money transfer
