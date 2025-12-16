using System.Collections.Concurrent;
using System.Text;
using Newtonsoft.Json.Linq;

namespace Assignment14;

public static class Solve
{
    private static readonly HttpClient HttpClient = new()
    {
        Timeout = TimeSpan.FromSeconds(180)
    };
    public const string TopApiUrl = "http://127.0.0.1:8123";

    // -----------------------
    // assignment.log support
    // -----------------------
    private static readonly object LogLock = new();
    private static readonly string LogPath =
        Path.Combine(Directory.GetCurrentDirectory(), "assignment.log");

    private static void Log(string msg)
    {
        lock (LogLock)
        {
            File.AppendAllText(LogPath, msg + Environment.NewLine, Encoding.UTF8);
        }
    }

    // Tree writes must be thread-safe (Tree uses Dictionary<>)
    private static readonly object TreeLock = new();

    // Optional caches to avoid refetching same ids
    private static readonly ConcurrentDictionary<long, Person?> PersonCache = new();
    private static readonly ConcurrentDictionary<long, Family?> FamilyCache = new();

    // This function retrieves JSON from the server
    public static async Task<JObject?> GetDataFromServerAsync(string url)
    {
        // Server can be busy -> retry on non-200 / empty JSON / exceptions
        const int maxAttempts = 8;

        for (int attempt = 1; attempt <= maxAttempts; attempt++)
        {
            try
            {
                using var resp = await HttpClient.GetAsync(url);
                if (!resp.IsSuccessStatusCode)
                {
                    Log($"WARN non-200 {(int)resp.StatusCode} on {url} attempt {attempt}/{maxAttempts}");
                    await Task.Delay(BackoffMs(attempt));
                    continue;
                }

                var jsonString = await resp.Content.ReadAsStringAsync();
                if (string.IsNullOrWhiteSpace(jsonString) || jsonString.Trim() == "{}")
                {
                    Log($"WARN empty-json on {url} attempt {attempt}/{maxAttempts}");
                    await Task.Delay(BackoffMs(attempt));
                    continue;
                }

                return JObject.Parse(jsonString);
            }
            catch (Exception e)
            {
                Log($"WARN exception on {url} attempt {attempt}/{maxAttempts}: {e.Message}");
                await Task.Delay(BackoffMs(attempt));
            }
        }

        Log($"ERROR giving up on {url}");
        return null;
    }

    private static int BackoffMs(int attempt)
    {
        // exponential backoff + jitter
        int baseMs = 120 * (int)Math.Pow(2, Math.Min(attempt - 1, 5));
        int jitter = Random.Shared.Next(0, 80);
        return baseMs + jitter;
    }

    // This function takes in a person ID and retrieves a Person object
    // Hint: It can be used in a "new List<Task<Person?>>()" list
    private static async Task<Person?> FetchPersonAsync(long personId)
    {
        if (personId <= 0) return null;

        if (PersonCache.TryGetValue(personId, out var cached))
            return cached;

        var personJson = await Solve.GetDataFromServerAsync($"{Solve.TopApiUrl}/person/{personId}");
        var person = personJson != null ? Person.FromJson(personJson.ToString()) : null;

        PersonCache.TryAdd(personId, person);
        return person;
    }

    // This function takes in a family ID and retrieves a Family object
    // Hint: It can be used in a "new List<Task<Family?>>()" list
    private static async Task<Family?> FetchFamilyAsync(long familyId)
    {
        if (familyId <= 0) return null;

        if (FamilyCache.TryGetValue(familyId, out var cached))
            return cached;

        var familyJson = await Solve.GetDataFromServerAsync($"{Solve.TopApiUrl}/family/{familyId}");
        var family = familyJson != null ? Family.FromJson(familyJson.ToString()) : null;

        FamilyCache.TryAdd(familyId, family);
        return family;
    }

    // ---------------------------------------------------------
    // Add family + all people (husband, wife, children) to tree
    // ---------------------------------------------------------
    private static async Task<(Person? husband, Person? wife)> AddFamilyAndPeopleAsync(Family fam, Tree tree)
    {
        // Fetch people in parallel
        var tasks = new List<Task<Person?>>();

        if (fam.HusbandId > 0) tasks.Add(FetchPersonAsync(fam.HusbandId));
        if (fam.WifeId > 0) tasks.Add(FetchPersonAsync(fam.WifeId));

        foreach (var childId in fam.Children)
        {
            if (childId > 0) tasks.Add(FetchPersonAsync(childId));
        }

        var results = await Task.WhenAll(tasks);

        // identify husband/wife from results
        Person? husband = results.FirstOrDefault(p => p != null && p.Id == fam.HusbandId);
        Person? wife = results.FirstOrDefault(p => p != null && p.Id == fam.WifeId);

        lock (TreeLock)
        {
            // Tree stores families/people in dictionaries => must lock
            tree.AddFamily(fam);

            foreach (var p in results)
            {
                if (p != null)
                    tree.AddPerson(p);
            }
        }

        return (husband, wife);
    }

    // =======================================================================================================
    // PART 1: DFS (recursive) + threads
    // Traversal rule for your Tree.cs:
    //   From a family -> go "up" to parents by using husband.ParentId and wife.ParentId
    // =======================================================================================================
    public static async Task<bool> DepthFS(long familyId, Tree tree)
    {
        if (familyId <= 0) return true;

        // clear log each run (optional, but nice)
        lock (LogLock) File.WriteAllText(LogPath, "");

        var visitedFamilies = new ConcurrentDictionary<long, bool>();
        await DepthFsInternal(familyId, tree, visitedFamilies);
        return true;
    }

    private static async Task DepthFsInternal(long familyId, Tree tree, ConcurrentDictionary<long, bool> visitedFamilies)
    {
        if (familyId <= 0) return;
        if (!visitedFamilies.TryAdd(familyId, true)) return;

        var fam = await FetchFamilyAsync(familyId);
        if (fam == null) return;

        var (husband, wife) = await AddFamilyAndPeopleAsync(fam, tree);

        // Next families are the parents of husband/wife (generations upwards)
        var next = new List<long>();
        if (husband != null && husband.ParentId > 0) next.Add(husband.ParentId);
        if (wife != null && wife.ParentId > 0) next.Add(wife.ParentId);

        // Threaded recursion
        var tasks = new List<Task>();
        foreach (var nextFamId in next.Distinct())
        {
            tasks.Add(DepthFsInternal(nextFamId, tree, visitedFamilies));
        }

        await Task.WhenAll(tasks);
    }

    // =======================================================================================================
    // PART 2: BFS (NO recursion) + threads
    // Same traversal rule: from family -> enqueue husband.ParentId and wife.ParentId
    // =======================================================================================================
    public static async Task<bool> BreathFS(long famid, Tree tree)
    {
        if (famid <= 0) return true;

        // clear log each run (optional)
        lock (LogLock) File.WriteAllText(LogPath, "");

        var visitedFamilies = new ConcurrentDictionary<long, bool>();
        var queue = new ConcurrentQueue<long>();

        visitedFamilies.TryAdd(famid, true);
        queue.Enqueue(famid);

        int workerCount = Math.Min(Environment.ProcessorCount * 8, 96);

        int inFlight = 0;
        var workers = new List<Task>();

        for (int i = 0; i < workerCount; i++)
        {
            workers.Add(Task.Run(async () =>
            {
                while (true)
                {
                    if (!queue.TryDequeue(out var familyId))
                    {
                        if (Volatile.Read(ref inFlight) == 0 && queue.IsEmpty)
                            return;

                        await Task.Delay(5);
                        continue;
                    }

                    Interlocked.Increment(ref inFlight);
                    try
                    {
                        var fam = await FetchFamilyAsync(familyId);
                        if (fam == null) continue;

                        var (husband, wife) = await AddFamilyAndPeopleAsync(fam, tree);

                        if (husband != null && husband.ParentId > 0)
                        {
                            if (visitedFamilies.TryAdd(husband.ParentId, true))
                                queue.Enqueue(husband.ParentId);
                        }

                        if (wife != null && wife.ParentId > 0)
                        {
                            if (visitedFamilies.TryAdd(wife.ParentId, true))
                                queue.Enqueue(wife.ParentId);
                        }
                    }
                    finally
                    {
                        Interlocked.Decrement(ref inFlight);
                    }
                }
            }));
        }

        await Task.WhenAll(workers);
        return true;
    }
}
