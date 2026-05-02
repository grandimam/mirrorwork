/*
    Written by Bohdan Shtepan <bohdan@shtepan.com>, February 2025
 */

CREATE TABLE accounts (
    account_id INT PRIMARY KEY AUTO_INCREMENT,
    balance DECIMAL(18,2) NOT NULL CHECK (balance >= 0),
    version INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

BEGIN TRANSACTION;
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;

SELECT balance INTO @sender_balance FROM accounts WHERE id = 1;
IF @sender_balance < 100 THEN
    ROLLBACK;
    RAISE EXCEPTION 'Insufficient funds';
END IF;

UPDATE accounts
SET balance = balance - 100
WHERE id = 1;

UPDATE accounts
SET balance = balance + 100
WHERE id = 2;

COMMIT;
