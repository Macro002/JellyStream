using System;
using System.Diagnostics;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging;
using Newtonsoft.Json.Linq;

namespace Jellyfin.Plugin.JellyStream.Api;

[ApiController]
[Route("JellyStream/Update")]
public class UpdateController : ControllerBase
{
    private readonly ILogger<UpdateController> _logger;

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

            _logger.LogInformation("Starting background update for series: {Name} from {Site}", name, site);

            // Start the update in the background so we don't timeout
            _ = Task.Run(async () =>
            {
                try
                {
                    await CallManualUpdater(name, site);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Background task error for {Name}", name);
                }
            });

            // Return immediately with accepted status
            return Ok(new UpdateResult
            {
                Message = $"Update started for '{name}'. This will run in the background and may take several minutes. Check the Jellyfin logs for progress."
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error starting update for series");
            return StatusCode(500, ex.Message);
        }
    }

    private async Task CallManualUpdater(string seriesName, string site)
    {
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = "python3",
                Arguments = $"/opt/JellyStream/utils/manual_updater.py --plugin --site {site} --series-name \"{seriesName}\" --json",
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

            var output = await process.StandardOutput.ReadToEndAsync();
            var error = await process.StandardError.ReadToEndAsync();

            await process.WaitForExitAsync();

            // Parse JSON output
            if (!string.IsNullOrWhiteSpace(output))
            {
                try
                {
                    var result = JObject.Parse(output);
                    if (result["success"]?.Value<bool>() == true)
                    {
                        var episodes = result["episodes"]?.Value<int>() ?? 0;
                        _logger.LogInformation("✅ Update complete for {Name}: {Episodes} episodes", seriesName, episodes);
                    }
                    else
                    {
                        var errorMsg = result["error"]?.ToString() ?? "Unknown error";
                        _logger.LogError("❌ Update failed for {Name}: {Error}", seriesName, errorMsg);
                    }
                }
                catch
                {
                    // Not JSON, just log it
                    _logger.LogInformation("Output: {Output}", output);
                }
            }

            if (!string.IsNullOrWhiteSpace(error))
            {
                _logger.LogWarning("Stderr: {Error}", error);
            }

            if (process.ExitCode != 0)
            {
                _logger.LogError("manual_updater.py exited with code {Code}", process.ExitCode);
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
}
