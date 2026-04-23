# Written by Bohdan Shtepan <bohdan@shtepan.com>, February 2025

from threading import Thread
from queue import Queue
from decimal import Decimal


class Account:
    def __init__(self, account_id: int, balance: Decimal = Decimal(0)):
        self.account_id = account_id
        self.balance = balance

    def deposit(self, amount: Decimal) -> None:
        self.balance += amount

    def withdraw(self, amount: Decimal) -> bool:
        if self.balance >= amount:
            self.balance -= amount
            return True
        return False


# Ledger lock-free solution
class Ledger:
    def __init__(self):
        self.transaction_queue = Queue()
        self.processing_thread = Thread(target=self.process_transactions, daemon=True)
        self.processing_thread.start()

    def transfer_money(self, from_account: Account, to_account: Account, amount: Decimal):
        self.transaction_queue.put((from_account, to_account, amount))

    def process_transactions(self):
        while True:
            from_account, to_account, amount = self.transaction_queue.get()
            if from_account.withdraw(amount):
                to_account.deposit(amount)
            self.transaction_queue.task_done()
