/*
 * Course    : CSE 351
 * Assignment: 14
 */
using System;
using System.IO;
using System.Threading.Tasks;
using Assignment14;
 public const string TopApiUrl = "http://127.0.0.1:8123";
class Program
{
    public static async Task run_part(long startId, int generations, string title,
        Func<long, Tree, Task<bool>> func)
    {
        // Tell server to build a new tree for this run
        var startData = await Solve.GetDataFromServerAsync($"{Solve.TopApiUrl}/start/{generations}");
        Logger.Info($"Server start response: {startData}");

        Logger.Info("".PadRight(45, '#'));
        Logger.Info($"{title}: {generations} generations");
        Logger.Info("".PadRight(45, '#'));

        var timer = System.Diagnostics.Stopwatch.StartNew();

        var tree = new Tree(startId);
        await func(startId, tree);

        timer.Stop();
        double totalTime = timer.Elapsed.TotalSeconds;

        var serverData = await Solve.GetDataFromServerAsync($"{Solve.TopApiUrl}/end");
        Logger.Info($"Server end response: {serverData}");

        Logger.Info($"total_time                  : {totalTime:F5}");
        Logger.Info($"Generations                 : {generations}");

        Logger.Info("STATS        Retrieved | Server details");
        Logger.Info($"People  : {tree.PersonCount,12:N0} | {serverData?["people"],14:N0}");
        Logger.Info($"Families: {tree.FamilyCount,12:N0} | {serverData?["families"],14:N0}");
        Logger.Info($"API Calls                   : {serverData?["api"]}");
        Logger.Info($"Max number of threads       : {serverData?["threads"]}");
        Logger.Info("");
    }

    static async Task Main()
    {
        // ✅ This creates assignment.log in the folder where you run dotnet run
        string logPath = Path.GetFullPath("assignment.log");
        Logger.Configure(minimumLevel: LogLevel.Debug, logToFile: true, filePath: logPath);
        Logger.Info($"assignment.log created at: {logPath}");

        // Get the starting family id
        var data = await Solve.GetDataFromServerAsync($"{Solve.TopApiUrl}");
        if (data == null)
        {
            Logger.Error("Could not connect to server. Is server.py running?");
            return;
        }

        long start_id = (long)data["start_family_id"];
        Logger.Info($"start_family_id: {start_id}");

        // Read runs.txt like: "1,6" or "2,6"
        foreach (string line in File.ReadLines("runs.txt"))
        {
            if (string.IsNullOrWhiteSpace(line)) continue;

            string[] parts = line.Split(',');
            if (parts.Length < 2) continue;

            if (!int.TryParse(parts[0], out int partToRun)) continue;
            if (!int.TryParse(parts[1], out int generations)) continue;

            Logger.Info($"RUN FROM runs.txt -> part={partToRun}, generations={generations}");

            if (partToRun == 1)
            {
                Logger.Info("START DFS");
                await run_part(start_id, generations, "Depth First Search", Solve.DepthFS);
                Logger.Info("END DFS");
            }
            else if (partToRun == 2)
            {
                Logger.Info("START BFS");
                await run_part(start_id, generations, "Breath First Search", Solve.BreathFS);
                Logger.Info("END BFS");
            }
        }
    }
}
