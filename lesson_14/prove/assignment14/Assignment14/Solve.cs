using System.Collections.Concurrent;
using Newtonsoft.Json.Linq;

namespace Assignment14;

public static class Solve
{
    private static readonly HttpClient HttpClient = new()
    {
        Timeout = TimeSpan.FromSeconds(180)
    };

    public const string TopApiUrl = "http://127.0.0.1:8123";

    // Tree uses dictionaries -> protect mutations
    private static readonly object TreeLock = new();

    // -----------------------------
    // Robust GET with retries
    // -----------------------------
    public static async Task<JObject?> GetDataFromServerAsync(string url)
    {
        const int retries = 50;
        const int delayMs = 10;

        for (int i = 0; i < retries; i++)
        {
            try
            {
                var jsonString = await HttpClient.GetStringAsync(url);

                if (string.IsNullOrWhiteSpace(jsonString))
                {
                    await Task.Delay(delayMs);
                    continue;
                }

                return JObject.Parse(jsonString);
            }
            catch (HttpRequestException)
            {
                await Task.Delay(delayMs);
            }
            catch (TaskCanceledException)
            {
                await Task.Delay(delayMs);
            }
            catch
            {
                await Task.Delay(delayMs);
            }
        }

        return null;
    }

    // -----------------------------
    // Fetch helpers (use your FromJson)
    // -----------------------------
    private static async Task<Family?> FetchFamilyAsync(long familyId)
    {
        if (familyId <= 0) return null;

        var json = await GetDataFromServerAsync($"{TopApiUrl}/family/{familyId}");
        return json != null ? Family.FromJson(json.ToString()) : null;
    }

    private static async Task<Person?> FetchPersonAsync(long personId)
    {
        if (personId <= 0) return null;

        var json = await GetDataFromServerAsync($"{TopApiUrl}/person/{personId}");
        return json != null ? Person.FromJson(json.ToString()) : null;
    }

    private static void AddFamilyIfMissing(Tree tree, Family family)
    {
        lock (TreeLock)
        {
            if (!tree.DoesFamilyExist(family.Id))
                tree.AddFamily(family);
        }
    }

    private static void AddPersonIfMissing(Tree tree, Person person)
    {
        lock (TreeLock)
        {
            if (!tree.DoesPersonExist(person.Id))
                tree.AddPerson(person);
        }
    }

    // ============================================================
    // PART 1: DFS (recursive) + parallel fetching of people
    // ============================================================
    public static async Task<bool> DepthFS(long startFamilyId, Tree tree)
    {
        var visitedFamilies = new ConcurrentDictionary<long, byte>();

        async Task DfsAsync(long familyId)
        {
            if (familyId <= 0) return;

            // DFS visited set
            if (!visitedFamilies.TryAdd(familyId, 0))
                return;

            // 1) Get family
            var family = await FetchFamilyAsync(familyId);
            if (family == null) return;

            AddFamilyIfMissing(tree, family);

            // 2) Fetch husband/wife/children in parallel
            var personIds = new List<long>();
            if (family.HusbandId > 0) personIds.Add(family.HusbandId);
            if (family.WifeId > 0) personIds.Add(family.WifeId);
            foreach (var c in family.Children)
                if (c > 0) personIds.Add(c);

            var tasks = personIds.Select(async pid =>
            {
                var p = await FetchPersonAsync(pid);
                if (p != null) AddPersonIfMissing(tree, p);
            });

            await Task.WhenAll(tasks);

            // 3) DFS recursion: go to parents of husband and wife
            long husbandParentFam = 0;
            long wifeParentFam = 0;

            lock (TreeLock)
            {
                var husband = family.HusbandId > 0 ? tree.GetPerson(family.HusbandId) : null;
                var wife = family.WifeId > 0 ? tree.GetPerson(family.WifeId) : null;

                if (husband != null) husbandParentFam = husband.ParentId;
                if (wife != null) wifeParentFam = wife.ParentId;
            }

            if (husbandParentFam > 0) await DfsAsync(husbandParentFam);
            if (wifeParentFam > 0) await DfsAsync(wifeParentFam);
        }

        await DfsAsync(startFamilyId);
        return true;
    }

    // ============================================================
    // PART 2: BFS (no recursion) + worker tasks
    // ============================================================
    public static async Task<bool> BreathFS(long startFamilyId, Tree tree)
    {
        var visitedFamilies = new ConcurrentDictionary<long, byte>();
        var queue = new ConcurrentQueue<long>();

        visitedFamilies.TryAdd(startFamilyId, 0);
        queue.Enqueue(startFamilyId);

        // Increase if needed; IO-bound so more helps until server saturates
        int workerCount = 30;

        // Lets workers know when the whole BFS is done
        int inFlight = 0;

        async Task Worker()
        {
            while (true)
            {
                if (!queue.TryDequeue(out var fid))
                {
                    if (Volatile.Read(ref inFlight) == 0)
                        break;

                    await Task.Delay(1);
                    continue;
                }

                Interlocked.Increment(ref inFlight);

                try
                {
                    var family = await FetchFamilyAsync(fid);
                    if (family == null) continue;

                    AddFamilyIfMissing(tree, family);

                    // Fetch everyone in this family in parallel
                    var personIds = new List<long>();
                    if (family.HusbandId > 0) personIds.Add(family.HusbandId);
                    if (family.WifeId > 0) personIds.Add(family.WifeId);
                    foreach (var c in family.Children)
                        if (c > 0) personIds.Add(c);

                    var tasks = personIds.Select(async pid =>
                    {
                        var p = await FetchPersonAsync(pid);
                        if (p != null) AddPersonIfMissing(tree, p);
                    });

                    await Task.WhenAll(tasks);

                    // Enqueue parent families (BFS expansion)
                    long husbandParentFam = 0;
                    long wifeParentFam = 0;

                    lock (TreeLock)
                    {
                        var husband = family.HusbandId > 0 ? tree.GetPerson(family.HusbandId) : null;
                        var wife = family.WifeId > 0 ? tree.GetPerson(family.WifeId) : null;

                        if (husband != null) husbandParentFam = husband.ParentId;
                        if (wife != null) wifeParentFam = wife.ParentId;
                    }

                    if (husbandParentFam > 0 && visitedFamilies.TryAdd(husbandParentFam, 0))
                        queue.Enqueue(husbandParentFam);

                    if (wifeParentFam > 0 && visitedFamilies.TryAdd(wifeParentFam, 0))
                        queue.Enqueue(wifeParentFam);
                }
                finally
                {
                    Interlocked.Decrement(ref inFlight);
                }
            }
        }

        var workers = Enumerable.Range(0, workerCount)
            .Select(_ => Task.Run(Worker))
            .ToArray();

        await Task.WhenAll(workers);
        return true;
    }
}
