using System.Diagnostics;

namespace assignment11;

public class Assignment11
{
    private const long START_NUMBER = 10_000_000_000;
    private const int RANGE_COUNT = 1_000_000;

    private const int DEFAULT_WORKER_COUNT= 10;

    private static readonly Queue<long>_workQueue = new ();
    private static readonly object _queueLock = new ();

    private static readonly object _consoleLock = new ();

    private static bool _addingCompleted = false;   
    private static int _numbersProcessed = 0;
    private static int _primeCount = 0;

    private static bool IsPrime(long n)
    {
        if (n <= 3) return n > 1;
        if (n % 2 == 0 || n % 3 == 0) return false;

        for (long i = 5; i * i <= n; i = i + 6)
        {
            if (n % i == 0 || n % (i + 2) == 0)
                return false;
        }
        return true;
    }

    /// <summary>
        /// Take a number from the queue. Returns false when all work is done.
        /// </summary>
        private static bool TryDequeue(out long value)
        {
            lock (_queueLock)
            {
                // While there is no work but more might come, wait.
                while (_workQueue.Count == 0 && !_addingCompleted)
                {
                    Monitor.Wait(_queueLock);
                }

                // If queue is empty and no more will be added, we are done.
                if (_workQueue.Count == 0 && _addingCompleted)
                {
                    value = 0;
                    return false;
                }

                value = _workQueue.Dequeue();
                return true;
            }
        }

        /// <summary>
        /// Worker thread method: gets numbers from the queue and tests them.
        /// </summary>
        private static void Worker()
        {
            while (TryDequeue(out long number))
            {
                Interlocked.Increment(ref _numbersProcessed);

                if (IsPrime(number))
                {
                    Interlocked.Increment(ref _primeCount);

                    // Protect console so output is not jumbled
                    lock (_consoleLock)
                    {
                        Console.Write($"{number}, ");
                    }
                }
            }
        }

        public static void Main(string[] args)
        {
            int workerCount = DEFAULT_WORKER_COUNT;

            // Optional: allow user to specify worker count on command line
            if (args.Length > 0 &&
                int.TryParse(args[0], out int parsed) &&
                parsed > 0)
            {
                workerCount = parsed;
            }

            Console.WriteLine("Prime numbers found:");

            var stopwatch = Stopwatch.StartNew();

            // 1. Start worker threads
            Thread[] workers = new Thread[workerCount];
            for (int i = 0; i < workerCount; i++)
            {
                workers[i] = new Thread(Worker);
                workers[i].Start();
            }

            // 2. Main thread adds numbers to the queue (producer)
            lock (_queueLock)
            {
                for (long i = START_NUMBER; i < START_NUMBER + RANGE_COUNT; i++)
                {
                    _workQueue.Enqueue(i);
                    // Wake up one waiting worker
                    Monitor.Pulse(_queueLock);
                }

                // Signal that no more numbers will be added
                _addingCompleted = true;
                Monitor.PulseAll(_queueLock);
            }

            // 3. Wait for all workers to finish
            foreach (Thread t in workers)
            {
                t.Join();
            }

            stopwatch.Stop();

            Console.WriteLine(); // new line after prime list
            Console.WriteLine();

            Console.WriteLine($"Numbers processed = {_numbersProcessed}");
            Console.WriteLine($"Primes found      = {_primeCount}");  // should be 43427
            Console.WriteLine($"Total time        = {stopwatch.Elapsed}");
        }
    }
