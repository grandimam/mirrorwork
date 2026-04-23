/*
    Written by Bohdan Shtepan <bohdan@shtepan.com>, February 2025
 */

START TRANSACTION;
-- Deduct money from sender if version matches (ensures no concurrent modification)
UPDATE accounts
SET balance = balance - 100, version = version + 1
WHERE account_id = 1 AND balance >= 100 AND version = (SELECT version FROM accounts WHERE account_id = 1);
-- Check if the update succeeded
SELECT ROW_COUNT() INTO @rows_affected;
IF @rows_affected = 0 THEN
    ROLLBACK;
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Optimistic Locking Failed: Balance too low or version mismatch';
END IF;
-- Credit money to receiver, also ensuring version consistency
UPDATE accounts
SET balance = balance + 100, version = version + 1
WHERE account_id = 2 AND version = (SELECT version FROM accounts WHERE account_id = 2);
-- Check if the update succeeded
SELECT ROW_COUNT() INTO @rows_affected;
IF @rows_affected = 0 THEN
    ROLLBACK;
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Optimistic Locking Failed: Version mismatch on destination account';
END IF;
COMMIT;
