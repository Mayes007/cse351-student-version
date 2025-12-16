using System.Collections.Concurrent;
using Newtonsoft.Json.Linq;

namespace Assignment14;

public static class Solve
{
    private static readonly HttpClient HttpClient = new()
    {
        Timeout = TimeSpan.FromSeconds(180)
    };

   

    // Prevent overwhelming the server (still very fast)
    private static readonly SemaphoreSlim HttpGate = new(initialCount: 200, maxCount: 200);

    private const int MaxRetries = 6;
    private const int BaseDelayMs = 60;

    // =======================================================================================================
    // Provided: basic GET that returns JObject or null
    public static async Task<JObject?> GetDataFromServerAsync(string url)
    {
        try
        {
            var jsonString = await HttpClient.GetStringAsync(url);

            // Server sometimes returns empty/{} when overloaded
            if (string.IsNullOrWhiteSpace(jsonString) || jsonString.Trim() == "{}")
                return null;

            return JObject.Parse(jsonString);
        }
        catch (Exception ex)
        {
            Logger.Warning($"Error fetching {url}", ex);
            return null;
        }
    }

    // =======================================================================================================
    // Retry wrapper to survive server overload
    private static async Task<JObject?> GetWithRetryAsync(string url)
    {
        for (int attempt = 1; attempt <= MaxRetries; attempt++)
        {
            await HttpGate.WaitAsync();
            try
            {
                var obj = await GetDataFromServerAsync(url);
                if (obj != null) return obj;
            }
            finally
            {
                HttpGate.Release();
            }

            int delay = BaseDelayMs * (int)Math.Pow(2, attempt - 1);
            delay = Math.Min(delay, 1000);
            await Task.Delay(delay);
        }

        Logger.Warning($"FAILED after {MaxRetries} retries: {url}");
        return null;
    }

    // =======================================================================================================
    // Fetch Person by id
    private static async Task<Person?> FetchPersonAsync(long personId)
    {
        if (personId <= 0) return null;

        var obj = await GetWithRetryAsync($"{TopApiUrl}/person/{personId}");
        return obj == null ? null : Person.FromJson(obj.ToString());
    }

    // =======================================================================================================
    // Fetch Family by id
    private static async Task<Family?> FetchFamilyAsync(long familyId)
    {
        if (familyId <= 0) return null;

        var obj = await GetWithRetryAsync($"{TopApiUrl}/family/{familyId}");
        return obj == null ? null : Family.FromJson(obj.ToString());
    }

    // =======================================================================================================
    // Fetch a family and ALL people in it (husband, wife, children), then add to Tree
    private static async Task<(Family? fam, Person? husb, Person? wife)> FetchAndAddFamilyAsync(long familyId, Tree tree)
    {
        var fam = await FetchFamilyAsync(familyId);
        if (fam == null) return (null, null, null);

        // Store family
        if (tree.GetFamily(fam.Id) == null)
            tree.AddFamily(fam);

        // Fetch husband/wife/children in parallel
        Task<Person?> husbTask = FetchPersonAsync(fam.HusbandId);
        Task<Person?> wifeTask = FetchPersonAsync(fam.WifeId);

        var childTasks = fam.Children.Select(FetchPersonAsync).ToList();

        var all = new List<Task<Person?>>(2 + childTasks.Count) { husbTask, wifeTask };
        all.AddRange(childTasks);

        var people = await Task.WhenAll(all);

        // Store people
        foreach (var p in people)
        {
            if (p == null) continue;
            if (!tree.PersonExists(p.Id))
                tree.AddPerson(p);
        }

        return (fam, await husbTask, await wifeTask);
    }

    // =======================================================================================================
    // PART 1: DFS (recursive) + threading
    public static async Task<bool> DepthFS(long familyId, Tree tree)
    {
        var visitedFamilies = new ConcurrentDictionary<long, byte>();

        async Task DFS(long famId)
        {
            // base cases
            if (famId <= 0) return;
            if (!visitedFamilies.TryAdd(famId, 0)) return;

            // Visit current node (family) and add people
            var (_, husb, wife) = await FetchAndAddFamilyAsync(famId, tree);

            // DFS recursion target: parents' family ids (from Person.ParentId)
            long hParentFam = husb?.ParentId ?? 0;
            long wParentFam = wife?.ParentId ?? 0;

            // THREADING: run both parent branches at the same time
            var tasks = new List<Task>(2);
            if (hParentFam > 0) tasks.Add(DFS(hParentFam));
            if (wParentFam > 0) tasks.Add(DFS(wParentFam));

            if (tasks.Count > 0)
                await Task.WhenAll(tasks);
        }

        Logger.Info("Running Depth First Search (recursive)...");
        await DFS(familyId);
        Logger.Info("DFS done.");
        return true;
    }

    // =======================================================================================================
    // PART 2: BFS (NO recursion) + threading
    public static async Task<bool> BreathFS(long famid, Tree tree)
    {
        var visitedFamilies = new ConcurrentDictionary<long, byte>();
        var queue = new ConcurrentQueue<long>();
        queue.Enqueue(famid);

        Logger.Info("Running Breadth First Search (iterative)...");
        
        while (!queue.IsEmpty)
        {
            // Take a snapshot "layer" to process concurrently
            var level = new List<long>();
            while (queue.TryDequeue(out long id))
            {
                level.Add(id);
                if (level.Count >= 2000) break; // keep batches reasonable
            }

            // Deduplicate & skip visited
            level = level.Where(id => id > 0 && visitedFamilies.TryAdd(id, 0)).Distinct().ToList();
            if (level.Count == 0) continue;

            // THREADING: process all families in this batch concurrently
            var tasks = level.Select(async id =>
            {
                var (_, husb, wife) = await FetchAndAddFamilyAsync(id, tree);
                return (h: husb?.ParentId ?? 0, w: wife?.ParentId ?? 0);
            }).ToList();

            var parents = await Task.WhenAll(tasks);

            // Enqueue next families (parents) for BFS order
            foreach (var (h, w) in parents)
            {
                if (h > 0) queue.Enqueue(h);
                if (w > 0) queue.Enqueue(w);
            }
        }

        Logger.Info("BFS done.");
        return true;
    }
}
