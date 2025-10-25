"""
Course    : CSE 351
Assignment: 04
Student   : Samantha Mayes

Instructions:
    - review instructions in the course

In order to retrieve a weather record from the server, Use the URL:

f'{TOP_API_URL}/record/{name}/{recno}

where:

name: name of the city
recno: record number starting from 0

"""
import threading
import queue
import time
import random
from collections import defaultdict
from common import *

from cse351 import *

THREADS = 100               # TODO - set for your program
WORKERS = 10
RECORDS_TO_RETRIEVE = 5000  # Don't change


# ---------------------------------------------------------------------------
def retrieve_weather_data(cmd_q:"queue.Queue", data_q: "queue.Queue"):
    # TODO - fill out this thread function (and arguments)
 
    while True:
        item= cmd_q.get()
        if item is None:
            cmd_q
            break

        city, recno = item
        rec = get_data_from_server(f'{TOP_API_URL}/record/{city}/{recno}')

        date=rec("date")or rec.get("day") or rec.get("d")
        temp=rec.get("temperature")
        if temp is None:
            temp = rec.get("temp")

        data_q.put((city, date, float(temp)))
        cmd_q.task_done()

    ...


# ---------------------------------------------------------------------------
# TODO - Create Worker threaded class
class Worker(threading.Thread):

    def __init__(self, data_q: "queue.Queue", noaa: "NOAA"):
        super().__init__(daemon=True)
        self.data_q = data_q
        self.noaa = noaa

    def run(self):
        while True:
            item = self.data_q.get()
            if item is None:
                break

            city, date, temp = item
            self.noaa.add_record(city, date, temp)
            self.data_q.task_done()

   
# ---------------------------------------------------------------------------
# TODO - Complete this class
class NOAA:

    def __init__(self):
        self.temps= defaultdict(list) 
        self.lock=threading.Lock()

    def add_record(self, city:str, date: str, temp: float):
        with self.lock:
            self.temps[city].append(temp)

        ...

    def get_temp_details(self, city: str) -> float:
        with self.lock:
         temps = self.temps.get(city, [])
        if not temps:
                return sum(temps) / len(temps)
        return 0.0
        avg=sum(temps)/len(temps)
        return round(avg,4)

# ---------------------------------------------------------------------------
def verify_noaa_results(noaa):

    answers = {
        'sandiego': 14.5004,
        'philadelphia': 14.865,
        'san_antonio': 14.638,
        'san_jose': 14.5756,
        'new_york': 14.6472,
        'houston': 14.591,
        'dallas': 14.835,
        'chicago': 14.6584,
        'los_angeles': 15.2346,
        'phoenix': 12.4404,
    }

    print()
    print('NOAA Results: Verifying Results')
    print('===================================')
    for name in CITIES:
        answer = answers[name]
        avg = noaa.get_temp_details(name)

        if abs(avg - answer) > 0.00001:
            msg = f'FAILED  Expected {answer}'
        else:
            msg = f'PASSED'
        print(f'{name:>15}: {avg:<10} {msg}')
    print('===================================')


# ---------------------------------------------------------------------------
def main():

    log = Log(show_terminal=True, filename_log='assignment.log')
    log.start_timer()

    noaa = NOAA()

    # Start server
    data = get_data_from_server(f'{TOP_API_URL}/start')

    # Get all cities number of records
    print('Retrieving city details')
    city_details = {}
    name = 'City'
    print(f'{name:>15}: Records')
    print('===================================')
    for name in CITIES:
        city_details[name] = get_data_from_server(f'{TOP_API_URL}/city/{name}')
        print(f'{name:>15}: Records = {city_details[name]['records']:,}')
    print('===================================')

records = RECORDS_TO_RETRIEVE

def run_threads(noaa, city_details, log=None):
    # TODO - Create any queues, pipes, locks, barriers you need
    cmd_q = queue.Queue(maxsize=10)
    data_q = queue.Queue(maxsize=10)

    # TODO - Create and start your worker threads
    workers = [Worker(data_q, noaa) for _ in range(WORKERS)]
    for w in workers:
        w.start()

    # TODO - Create and start your retriever threads
    retrievers = [
        threading.Thread(target=retrieve_weather_data, args=(cmd_q, data_q))
        for _ in range(THREADS)
    ]
    for t in retrievers:
        t.start()

    # TODO - Fill the command queue with work
    for _ in range(records):
        for name in CITIES:
            recs = city_details[name]['records']
            recno = random.randint(0, recs - 1)
            cmd_q.put((name, recno))

    # TODO - wait for all work to be done
    cmd_q.join()
    data_q.join()

    # stop retriever threads
    for _ in range(THREADS):
        cmd_q.put(None)
    for r in retrievers:
        r.join()

    # stop worker threads
    for _ in range(WORKERS):
        data_q.put(None)
    for w in workers:
        w.join()
    
    # print the results
    print()
    print('NOAA Results:')
    print('===================================')
    for name in CITIES:
        avg = noaa.get_temp_details(name)
        print(f'{name:>15}: {avg:<10}')
    print('===================================')
    print(f'Total records processed: {records * len(CITIES):,}')
    # End server - don't change below
    data = get_data_from_server(f'{TOP_API_URL}/end')
    print(data)

    verify_noaa_results(noaa)

    # log.stop_timer('Run time: ')

    if log is not None:
        log.stop_timer('Run time: ')

if __name__ == '__main__':
    main()
    # If you want to call run_threads, pass log as argument
    # Example:
    # log = Log(show_terminal=True, filename_log='assignment.log')
    # run_threads(noaa, city_details, log)
    main()

