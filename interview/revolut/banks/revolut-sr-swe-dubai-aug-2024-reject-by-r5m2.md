# Revolut | Sr SWE | Dubai | Aug 2024 | Reject

**Source:** [LeetCode Discuss](https://leetcode.com/discuss/post/6074797/revolut-sr-swe-dubai-aug-2024-reject-by-r5m27/)
**Posted by:** Anonymous User
**Date:** November 23, 2024
**Views:** 2,331
**Tags:** Revolut · interview experience · Interview

---

## Role Details

| Field          | Detail                   |
| -------------- | ------------------------ |
| **Role**       | Senior Software Engineer |
| **Location**   | Dubai                    |
| **Date**       | August 2024              |
| **Outcome**    | Rejected                 |
| **Comp Range** | 350K–450K AED            |

---

## Observations

It was evident that Revolut was specifically looking for a **Java expert with experience in
payment gateway systems**, which the candidate believed should have been clearly mentioned
in the job description.

---

## Interview Process

### Round 1 — Initial HR Round

Discussed the job description and interview process. The HR team was quite helpful and
provided an outline of the question scope for each round.

---

### Round 2 — Coding Round

**Problem:** Design a load balancer for 10 servers and write corresponding test cases.

> For both rounds, the expectation was to write **production-ready code**, as if it would
> be deployed immediately — quite a high bar for an interview scenario.

---

### Round 3 — Technical Discussion

Two tasks were given:

1. **Java Task:** Implement a Java method to process a payment transaction from Account A
   to Account B.
2. **SQL Task:** Convert the same payment transaction logic into an SQL implementation.

Again, **production-ready code** was expected for both.

---

## Outcome

The candidate received a rejection email from HR with detailed feedback, specifically
highlighting the **inability to write a production-level SQL version** of the payment
transaction problem.

---

## Reference Solution — Payment Transaction (Java)

> _[for reference, please validate on your own]_

```java
package revolut;

import java.math.BigDecimal;

public class BankAccount {
    private final String accountId;
    private BigDecimal balance;

    public BankAccount(String accountId, BigDecimal initialBalance) {
        this.accountId = accountId;
        this.balance = initialBalance;
    }

    public String getAccountId() {
        return accountId;
    }

    public BigDecimal getBalance() {
        return balance;
    }

    public synchronized void deposit(BigDecimal amount) {
        if (amount.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Deposit amount must be greater than zero");
        }
        balance = balance.add(amount);
        System.out.println("Deposited " + amount + " to " + accountId
                + ", new balance: " + balance);
    }

    public synchronized void withdraw(BigDecimal amount) {
        if (amount.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Withdrawal amount must be greater than zero");
        }
        if (balance.compareTo(amount) < 0) {
            throw new IllegalArgumentException("Insufficient funds in account " + accountId);
        }
        balance = balance.subtract(amount);
        System.out.println("Withdrew " + amount + " from " + accountId
                + ", new balance: " + balance);
    }

    public static void transferMoney(BankAccount fromAccount, BankAccount toAccount,
                                     BigDecimal amount) {
        if (amount.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Transfer amount must be greater than zero");
        }

        // Consistent lock ordering to prevent deadlock
        BankAccount firstLock  = fromAccount;
        BankAccount secondLock = toAccount;

        if (fromAccount.getAccountId().compareTo(toAccount.getAccountId()) > 0) {
            firstLock  = toAccount;
            secondLock = fromAccount;
        }

        synchronized (firstLock) {
            synchronized (secondLock) {
                fromAccount.withdraw(amount);
                toAccount.deposit(amount);
                System.out.println("Transferred " + amount + " from "
                        + fromAccount.getAccountId() + " to " + toAccount.getAccountId());
            }
        }
    }

    public static void main(String[] args) {
        BankAccount accountA = new BankAccount("A123", new BigDecimal("5000.00"));
        BankAccount accountB = new BankAccount("B456", new BigDecimal("3000.00"));

        // Create threads to simulate concurrent transfers
        Thread t1 = new Thread(() -> transferMoney(accountA, accountB,
                new BigDecimal("1000.00")));
        Thread t2 = new Thread(() -> transferMoney(accountB, accountA,
                new BigDecimal("500.00")));

        t1.start();
        t2.start();

        try {
            t1.join();
            t2.join();
        } catch (InterruptedException e) {
            e.printStackTrace();
        }

        System.out.println("Final balance of Account A: " + accountA.getBalance());
        System.out.println("Final balance of Account B: " + accountB.getBalance());
    }
}
```

---

## What a Production-Ready SQL Solution Looks Like

The rejection was specifically for the SQL round. A passing answer would cover:
transactions, row-level locking, consistent lock order, balance validation, audit logging,
and rollback on failure.

```sql
-- Production-ready SQL: Transfer money from Account A to Account B
-- Uses a transaction with proper isolation, balance check, and rollback on failure

BEGIN TRANSACTION;

-- Lock both rows to prevent concurrent modification (SELECT FOR UPDATE)
-- Always lock in consistent order (lower account_id first) to prevent deadlock
SELECT balance
FROM accounts
WHERE account_id IN ('A123', 'B456')
ORDER BY account_id
FOR UPDATE;

DO $$
DECLARE
  v_balance NUMERIC;
  v_amount  NUMERIC  := 1000.00;
  v_from    VARCHAR  := 'A123';
  v_to      VARCHAR  := 'B456';
BEGIN
  SELECT balance INTO v_balance
  FROM accounts
  WHERE account_id = v_from;

  IF v_balance < v_amount THEN
    RAISE EXCEPTION 'Insufficient funds in account %', v_from;
  END IF;

  UPDATE accounts
  SET    balance    = balance - v_amount,
         updated_at = NOW()
  WHERE  account_id = v_from;

  UPDATE accounts
  SET    balance    = balance + v_amount,
         updated_at = NOW()
  WHERE  account_id = v_to;

  -- Audit log
  INSERT INTO transactions (from_account, to_account, amount, created_at, status)
  VALUES (v_from, v_to, v_amount, NOW(), 'SUCCESS');

  COMMIT;

EXCEPTION
  WHEN OTHERS THEN
    ROLLBACK;
    INSERT INTO transactions
      (from_account, to_account, amount, created_at, status, error_msg)
    VALUES
      (v_from, v_to, v_amount, NOW(), 'FAILED', SQLERRM);
    RAISE;
END $$;
```

---

## Key Learning Points

### 1. Deadlock Prevention via Consistent Lock Ordering

The Java solution compares `accountId` strings and **always acquires the lock on the
lexicographically smaller ID first**. This guarantees all threads agree on lock acquisition
order, eliminating circular-wait — the root cause of deadlocks.

A naive implementation that does:

```java
synchronized (fromAccount) {
    synchronized (toAccount) { ... }
}
```

is vulnerable to deadlock when Thread 1 calls `transferMoney(A, B, ...)` and Thread 2
calls `transferMoney(B, A, ...)` concurrently.

Community commenter **saxe07** noted this must be based on a stable key (e.g., account
ID hash or string comparison) to guarantee the same sequence every time.

### 2. BigDecimal Over double/float for Money

Using `double` or `float` introduces floating-point precision errors, which is
unacceptable in financial systems. **Always use `java.math.BigDecimal`** and instantiate
it from a `String` (not a `double` literal) to avoid precision loss at construction time.

### 3. synchronized Methods vs synchronized Blocks

- `deposit()` and `withdraw()` use **method-level `synchronized`** — they lock on `this`
  (the account instance), preventing concurrent access to a single account's balance.
- `transferMoney()` uses **nested `synchronized` blocks** on two specific objects,
  enabling fine-grained locking across two accounts simultaneously.

### 4. The Production-Ready Bar at Revolut

Revolut's expectation during the interview was code that could be **deployed immediately**.
This means:

- Input validation with meaningful exception messages
- Thread safety for all concurrent paths
- Correct data types (`BigDecimal`, not `double`)
- Logging / audit trail
- Test cases alongside the implementation

### 5. SQL Transaction Essentials for Payments

A production SQL payment transfer must address all of:

| Concern                  | Mechanism                                   |
| ------------------------ | ------------------------------------------- |
| Atomicity                | `BEGIN` / `COMMIT` / `ROLLBACK`             |
| Prevent dirty reads      | `SELECT FOR UPDATE`                         |
| Prevent SQL deadlocks    | Lock rows in consistent order (ORDER BY id) |
| Insufficient funds check | Validate balance before UPDATE              |
| Audit trail              | Insert into a `transactions` log table      |
| Isolation level          | `REPEATABLE READ` or `SERIALIZABLE`         |

### 6. Test Cases Are Part of the Answer

Round 2 (load balancer) explicitly required test cases alongside the implementation.
Writing tests is part of what "production-ready" means at Revolut.

---

## Community Comments

**saxe07 — May 13, 2025**

> "Only issue I see here is a deadlock can arise while acquiring locks on the account, as
> the next call to the same `transferMoney` method can have the from and to account
> swapped. It's good to have some mechanism based on hash on the account number to get
> first and second lock as it will always give you the same locking sequence."

**kibif46583 — Nov 24, 2024**

> "Hi, it's very sorry to hear. Can you please tell your years of experience btw? Also,
> why was the expectation to write a SQL version of the Java impl?"

**bharathkalyans — Nov 25, 2024**

> "Hi, can you please mention your TC, Company name (if comfortable) and how you applied
> for this role? It would be really helpful."

**Ravi Thej Neeli — Nov 26, 2024**

> "Hi OP, How did you apply for the position? Via HR or careers?"

---

## Interview Prep Summary

| Area                 | What to Study                                                       |
| -------------------- | ------------------------------------------------------------------- |
| **Java Concurrency** | `synchronized`, `ReentrantLock`, deadlock prevention, lock ordering |
| **Financial Types**  | `BigDecimal`, why not `double`, string construction                 |
| **SQL Transactions** | `BEGIN/COMMIT/ROLLBACK`, `SELECT FOR UPDATE`, isolation levels      |
| **System Design**    | Load balancer design, consistent hashing, health checks             |
| **Code Quality**     | Input validation, exceptions, logging, test cases                   |
| **Domain Knowledge** | Payment gateway systems, double-entry bookkeeping                   |
