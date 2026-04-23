/*
    Written by Bohdan Shtepan <bohdan@shtepan.com>, February 2025
 */

START TRANSACTION;
-- Lock both accounts for the duration of the transaction
SELECT balance FROM accounts WHERE account_id = 1 FOR UPDATE;
SELECT balance FROM accounts WHERE account_id = 2 FOR UPDATE;
-- Check if sender has enough balance
SELECT balance INTO @sender_balance FROM accounts WHERE account_id = 1;
IF @sender_balance < 100 THEN
    ROLLBACK;
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Insufficient Balance';
END IF;
-- Transfer money
UPDATE accounts SET balance = balance - 100 WHERE account_id = 1;
UPDATE accounts SET balance = balance + 100 WHERE account_id = 2;
COMMIT;
