using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.Text;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging;
using Newtonsoft.Json.Linq;

namespace Jellyfin.Plugin.JellyStream.Api;

[Authorize(Policy = "RequiresElevation")]
[ApiController]
[Route("JellyStream/Update")]
public class UpdateController : ControllerBase
{
    private readonly ILogger<UpdateController> _logger;
    private static readonly ConcurrentDictionary<string, StringBuilder> _updateLogs = new();

    public UpdateController(ILogger<UpdateController> logger)
    {
        _logger = logger;
    }

    [HttpPost("Series")]
    public ActionResult<UpdateResult> UpdateSeries(
        [FromQuery] string name,
        [FromQuery] string site = "aniworld")
    {
        try
        {
            var config = Plugin.Instance?.Configuration;
            if (config == null)
            {
                return BadRequest("Plugin not configured");
            }

            var logKey = $"{site}:{name}";
            _updateLogs[logKey] = new StringBuilder();

            _logger.LogInformation("Starting background update for series: {Name} from {Site}", name, site);

            // Start the update in the background so we don't timeout
            _ = Task.Run(async () =>
            {
                try
                {
                    await CallManualUpdater(name, site, logKey);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Background task error for {Name}", name);
                    if (_updateLogs.TryGetValue(logKey, out var log))
                    {
                        log.AppendLine($"❌ Error: {ex.Message}");
                    }
                }
            });

            // Return immediately with accepted status
            return Ok(new UpdateResult
            {
                Message = $"Update started for '{name}'. Logs will appear below.",
                LogKey = logKey
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error starting update for series");
            return StatusCode(500, ex.Message);
        }
    }

    [HttpGet("Logs")]
    public ActionResult<LogResult> GetLogs([FromQuery] string key)
    {
        if (_updateLogs.TryGetValue(key, out var log))
        {
            return Ok(new LogResult { Logs = log.ToString() });
        }
        return NotFound();
    }

    private async Task CallManualUpdater(string seriesName, string site, string logKey)
    {
        try
        {
            var config = Plugin.Instance?.Configuration;
            var scriptPath = config?.ScriptPath ?? "/opt/JellyStream/utils/manual_updater.py";

            var psi = new ProcessStartInfo
            {
                FileName = "python3",
                Arguments = $"-u {scriptPath} --plugin --site {site} --series-name \"{seriesName}\"",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            _logger.LogInformation("Calling manual_updater.py for {Series} on {Site}", seriesName, site);

            using var process = Process.Start(psi);
            if (process == null)
            {
                _logger.LogError("Failed to start manual_updater.py");
                return;
            }

            if (!_updateLogs.TryGetValue(logKey, out var logBuilder))
            {
                return;
            }

            // Read output line by line as it comes
            while (!process.StandardOutput.EndOfStream)
            {
                var line = await process.StandardOutput.ReadLineAsync();
                if (!string.IsNullOrWhiteSpace(line))
                {
                    logBuilder.AppendLine(line);
                    _logger.LogInformation("{Line}", line);
                }
            }

            var error = await process.StandardError.ReadToEndAsync();
            if (!string.IsNullOrWhiteSpace(error))
            {
                logBuilder.AppendLine($"Error: {error}");
                _logger.LogWarning("Stderr: {Error}", error);
            }

            await process.WaitForExitAsync();

            if (process.ExitCode != 0)
            {
                logBuilder.AppendLine($"❌ Process exited with code {process.ExitCode}");
                _logger.LogError("manual_updater.py exited with code {Code}", process.ExitCode);
            }
            else
            {
                logBuilder.AppendLine("✅ Update completed successfully");
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error calling manual_updater.py");
        }
    }
}

public class UpdateResult
{
    public string Message { get; set; } = string.Empty;
    public string LogKey { get; set; } = string.Empty;
}

public class LogResult
{
    public string Logs { get; set; } = string.Empty;
}
