"""
Course    : CSE 351
Assignment: 02
Student   : <your name here>

Instructions:
    - review instructions in the course
"""

# Don't import any other packages for this assignment
import os
import random
import threading
from money import *
from cse351 import *

# ---------------------------------------------------------------------------
def main(): 

    print('\nATM Processing Program:')
    print('=======================\n')

    create_data_files_if_needed()

    # Load ATM data files
    data_files = get_filenames('data_files')
    # print(data_files)
    
    log = Log(show_terminal=True)
    log.start_timer()

    bank = Bank()

    # TODO - Add a ATM_Reader for each data file
    threads = []
    for path in data_files: 
        t=ATM_Reader(bank=bank, filename=path)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()


    test_balances(bank)

    log.stop_timer('Total time')


# ===========================================================================
class ATM_Reader():
    # TODO - implement this class here
    def __init__(self, bank, filename):
        super().__init__()
        self.bank = bank
        self.filename = filename

    def run(self):
        with open(self.filename, 'r') as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split(',')
                if len(parts) != 3:
                    continue
                acct_str, tc_type, amt_str = parts
                try:
                    account_id = int(acct_str)
                except ValueError:
                    continue

                amount = Money(amt_str)
                if tc_type == 'd':
                    self.bank.deposit(account_id, amount)
                elif tc_type == 'w':
                    self.bank.withdraw(account_id, amount)
                else:
                    continue


# ===========================================================================
class Account():
    # TODO - implement this class here
    def _int_(self):
        self.balance = Money('0.00')
        self.lock = threading.Lock()

    def deposit(self, amount):
        with self.lock:
            self.balance.add(amount)

    def withdraw(self, amount):
        with self.lock:
            self.balance.sub(amount)

    def get_balance(self):
        with self.lock:
            return Money(str(self.balance))



# ===========================================================================
class Bank():
    # TODO - implement this class here
    def __init__(self):
        self.accounts = {}
        self.lock = threading.Lock()

    def get_or_create(self, account_id):
        acct=self.accounts.get(account_id)
        if acct is not None:
            return acct
        with self.lock:
            acct = self.accounts.get(account_id)
            if acct is None:
                acct = Account()
                self._accounts[account_id] = acct
        return acct
    
    def deposit(self, account_id, amount):
        acct = self.get_or_create(account_id).acct.deposit(amount)

    def withdraw(self, account_id, amount):
        acct = self.get_or_create(account_id).acct.withdraw(amount)

    def get_balance(self, account_id):
        return self.get_or_create(account_id).acct.get_balance()
    ...


# ---------------------------------------------------------------------------

def get_filenames(folder):
    """ Don't Change """
    filenames = []
    for filename in os.listdir(folder):
        if filename.endswith(".dat"):
            filenames.append(os.path.join(folder, filename))
    return filenames

# ---------------------------------------------------------------------------
def create_data_files_if_needed():
    """ Don't Change """
    ATMS = 10
    ACCOUNTS = 20
    TRANSACTIONS = 250000

    sub_dir = 'data_files'
    if os.path.exists(sub_dir):
        return

    print('Creating Data Files: (Only runs once)')
    os.makedirs(sub_dir)

    random.seed(102030)
    mean = 100.00
    std_dev = 50.00

    for atm in range(1, ATMS + 1):
        filename = f'{sub_dir}/atm-{atm:02d}.dat'
        print(f'- {filename}')
        with open(filename, 'w') as f:
            f.write(f'# Atm transactions from machine {atm:02d}\n')
            f.write('# format: account number, type, amount\n')

            # create random transactions
            for i in range(TRANSACTIONS):
                account = random.randint(1, ACCOUNTS)
                trans_type = 'd' if random.randint(0, 1) == 0 else 'w'
                amount = f'{(random.gauss(mean, std_dev)):0.2f}'
                f.write(f'{account},{trans_type},{amount}\n')

    print()

# ---------------------------------------------------------------------------
def test_balances(bank):
    """ Don't Change """

    # Verify balances for each account
    correct_results = (
        (1, '59362.93'),
        (2, '11988.60'),
        (3, '35982.34'),
        (4, '-22474.29'),
        (5, '11998.99'),
        (6, '-42110.72'),
        (7, '-3038.78'),
        (8, '18118.83'),
        (9, '35529.50'),
        (10, '2722.01'),
        (11, '11194.88'),
        (12, '-37512.97'),
        (13, '-21252.47'),
        (14, '41287.06'),
        (15, '7766.52'),
        (16, '-26820.11'),
        (17, '15792.78'),
        (18, '-12626.83'),
        (19, '-59303.54'),
        (20, '-47460.38'),
    )

    wrong = False
    for account_number, balance in correct_results:
        bal = bank.get_balance(account_number)
        print(f'{account_number:02d}: balance = {bal}')
        if Money(balance) != bal:
            wrong = True
            print(f'Wrong Balance: account = {account_number}, expected = {balance}, actual = {bal}')

    if not wrong:
        print('\nAll account balances are correct')



if __name__ == "__main__":
    main()

