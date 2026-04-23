# Written by Bohdan Shtepan <bohdan@shtepan.com>, February 2025

from multiprocessing import Value

class Account:
    def __init__(self, account_id: int, balance: int = 0):
        self.account_id = account_id
        self.balance = Value('q', balance)

    def get_balance(self) -> Value:
        return self.balance.value

    def compare_and_swap(self, expected, new_value) -> bool:
        with self.balance.get_lock():
            if self.balance.value == expected:
                self.balance.value = new_value
                return True
            return False


# Ledger Compare-And-Swap
class Ledger:
    @staticmethod
    def transfer_money(from_account: Account, to_account: Account, amount: int) -> bool:
        while True:
            old_balance = from_account.get_balance()
            if old_balance < amount:
                return False
            if from_account.compare_and_swap(old_balance, old_balance - amount):
                to_account.compare_and_swap(to_account.get_balance(), to_account.get_balance() + amount)
                return True
