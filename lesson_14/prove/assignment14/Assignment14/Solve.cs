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

    // Tree uses normal dictionaries -> not thread safe
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

        // Optional: log a failure (won't crash your run)
        Logger.Write($"WARN: Failed after retries: {url}");
        return null;
    }

    // -----------------------------
    // Fetch Person
    // -----------------------------
    private static async Task<Person?> FetchPersonAsync(long personId)
    {
        if (personId <= 0) return null;

        var personJson = await GetDataFromServerAsync($"{TopApiUrl}/person/{personId}");
        return personJson != null ? Person.FromJson(personJson.ToString()) : null;
    }

    // -----------------------------
    // Fetch Family
    // -----------------------------
    private static async Task<Family?> FetchFamilyAsync(long familyId)
    {
        if (familyId <= 0) return null;

        var familyJson = await GetDataFromServerAsync($"{TopApiUrl}/family/{familyId}");
        return familyJson != null ? Family.FromJson(familyJson.ToString()) : null;
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

    private static (long husbandParentFam, long wifeParentFam) GetParentFamilyIds(Tree tree, Family family)
    {
        lock (TreeLock)
        {
            long hParent = 0;
            long wParent = 0;

            var husband = family.HusbandId > 0 ? tree.GetPerson(family.HusbandId) : null;
            var wife = family.WifeId > 0 ? tree.GetPerson(family.WifeId) : null;

            if (husband != null) hParent = husband.ParentId;
            if (wife != null) wParent = wife.ParentId;

            return (hParent, wParent);
        }
    }

    // =======================================================================================================
    // PART 1: DFS (recursive) + threads for speed
    // Must clearly be DFS: recursion explores parents immediately
    // =======================================================================================================
    public static async Task<bool> DepthFS(long familyId, Tree tree)
    {
        // visited families so we don't repeat work
        var visitedFamilies = new ConcurrentDictionary<long, byte>();

        async Task DfsAsync(long currentFamilyId)
        {
            if (currentFamilyId <= 0) return;

            // DFS visited check
            if (!visitedFamilies.TryAdd(currentFamilyId, 0))
                return;

            // Fetch family
            var family = await FetchFamilyAsync(currentFamilyId);
            if (family == null) return;

            AddFamilyIfMissing(tree, family);

            // Fetch husband/wife/children in parallel (this is the speed-up)
            var personIds = new List<long>();
            if (family.HusbandId > 0) personIds.Add(family.HusbandId);
            if (family.WifeId > 0) personIds.Add(family.WifeId);
            foreach (var childId in family.Children)
                if (childId > 0) personIds.Add(childId);

            var peopleTasks = personIds.Select(async pid =>
            {
                var person = await FetchPersonAsync(pid);
                if (person != null)
                    AddPersonIfMissing(tree, person);
            });

            await Task.WhenAll(peopleTasks);

            // DFS step: go deeper immediately to husband parents then wife parents
            var (husbandParentFam, wifeParentFam) = GetParentFamilyIds(tree, family);

            if (husbandParentFam > 0) await DfsAsync(husbandParentFam);
            if (wifeParentFam > 0) await DfsAsync(wifeParentFam);
        }

        Logger.Write("Solve.DepthFS started");
        await DfsAsync(familyId);
        Logger.Write("Solve.DepthFS finished");
        return true;
    }

    // =======================================================================================================
    // PART 2: BFS (NO recursion) + worker tasks
    // Must clearly be BFS: queue-based layer expansion
    // =======================================================================================================
    public static async Task<bool> BreathFS(long famid, Tree tree)
    {
        Logger.Write("Solve.BreathFS started");

        var visitedFamilies = new ConcurrentDictionary<long, byte>();
        var queue = new ConcurrentQueue<long>();

        if (famid <= 0) return true;

        visitedFamilies.TryAdd(famid, 0);
        queue.Enqueue(famid);

        // workers (I/O bound => more helps until server saturates)
        int workerCount = 30;
