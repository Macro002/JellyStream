using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging;
using Newtonsoft.Json;
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
    public async Task<ActionResult<UpdateResult>> UpdateSeries(
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

            string dataPath = site.ToLower() == "aniworld"
                ? config.AniworldDataPath
                : config.SerienstreamDataPath;

            string jellyfinPath = site.ToLower() == "aniworld"
                ? config.AniworldJellyfinPath
                : config.SerienstreamJellyfinPath;

            if (!System.IO.File.Exists(dataPath))
            {
                return NotFound($"Database file not found: {dataPath}");
            }

            _logger.LogInformation("Starting background update for series: {Name} from {Site}", name, site);

            // Start the update in the background so we don't timeout
            _ = Task.Run(async () =>
            {
                try
                {
                    await UpdateSeriesInternal(name, site, dataPath, jellyfinPath, config.ApiBaseUrl);
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

    private async Task UpdateSeriesInternal(string seriesName, string site, string dataPath, string jellyfinPath, string apiBaseUrl)
    {
        _logger.LogInformation("Loading database for {Name}", seriesName);

        // Load database to find the series
        var json = await System.IO.File.ReadAllTextAsync(dataPath);
        var data = JObject.Parse(json);
        var seriesArray = data["series"] as JArray;

        if (seriesArray == null)
        {
            _logger.LogError("No series found in database");
            return;
        }

        // Find the series by jellyfin_name or name
        JObject? targetSeries = null;
        int seriesIndex = -1;
        for (int i = 0; i < seriesArray.Count; i++)
        {
            var series = seriesArray[i] as JObject;
            var name = series?["jellyfin_name"]?.ToString() ?? series?["name"]?.ToString();
            if (name == seriesName)
            {
                targetSeries = series;
                seriesIndex = i;
                break;
            }
        }

        if (targetSeries == null)
        {
            _logger.LogError("Series not found in database: {Name}", seriesName);
            return;
        }

        var seriesUrl = targetSeries["url"]?.ToString();
        if (string.IsNullOrEmpty(seriesUrl))
        {
            _logger.LogError("Series URL is null or empty for {Name}", seriesName);
            return;
        }

        // Get the site directory
        var siteDir = Path.Combine("/opt/JellyStream/sites", site);
        var dataDir = Path.Combine(siteDir, "data");

        if (!Directory.Exists(siteDir))
        {
            _logger.LogError("Site directory not found: {Dir}", siteDir);
            return;
        }

        _logger.LogInformation("Scraping series from {Url}", seriesUrl);

        // Create a minimal catalog file
        var catalogData = new
        {
            script = "plugin_updater",
            total_series = 1,
            series = new[]
            {
                new
                {
                    name = targetSeries["name"]?.ToString() ?? seriesName,
                    url = seriesUrl
                }
            }
        };

        var catalogPath = Path.Combine(dataDir, "tmp_name_url.json");
        await System.IO.File.WriteAllTextAsync(catalogPath, JsonConvert.SerializeObject(catalogData, Formatting.Indented));

        try
        {
            // Run structure analyzer (script 2)
            _logger.LogInformation("Step 1/3: Analyzing structure...");
            if (!await RunPythonScript(siteDir, "2_url_season_episode_num.py", "--limit 1"))
            {
                _logger.LogError("Structure analysis failed");
                return;
            }

            // Run streams analyzer (script 3)
            _logger.LogInformation("Step 2/3: Analyzing streams...");
            if (!await RunPythonScript(siteDir, "3_language_streamurl.py", "--limit 1"))
            {
                _logger.LogError("Stream analysis failed");
                return;
            }

            // Run JSON structurer (script 4)
            _logger.LogInformation("Step 3/3: Structuring data...");
            if (!await RunPythonScript(siteDir, "4_json_structurer.py", ""))
            {
                _logger.LogError("JSON structuring failed");
                return;
            }

            // Load the newly structured data
            var newDataJson = await System.IO.File.ReadAllTextAsync(dataPath);
            var newData = JObject.Parse(newDataJson);
            var newSeriesArray = newData["series"] as JArray;

            if (newSeriesArray == null || newSeriesArray.Count == 0)
            {
                _logger.LogError("No updated data found");
                return;
            }

            // Replace the series in the original database
            var updatedSeries = newSeriesArray[0];
            seriesArray[seriesIndex] = updatedSeries;

            // Create backup
            var backupPath = dataPath + ".backup";
            if (System.IO.File.Exists(backupPath))
            {
                System.IO.File.Delete(backupPath);
            }
            System.IO.File.Copy(dataPath, backupPath);

            // Save updated database
            await System.IO.File.WriteAllTextAsync(dataPath, data.ToString(Formatting.Indented));
            _logger.LogInformation("Database updated successfully");

            // Regenerate .strm files for this series
            _logger.LogInformation("Regenerating .strm files...");
            var regenerator = new StrmRegenerator(apiBaseUrl, _logger);
            var strmCount = await regenerator.RegenerateSeries(updatedSeries as JObject ?? new JObject(), jellyfinPath);

            _logger.LogInformation("Update complete for {Name}: {Strm} .strm files created", seriesName, strmCount);
        }
        finally
        {
            // Clean up tmp file
            if (System.IO.File.Exists(catalogPath))
            {
                System.IO.File.Delete(catalogPath);
            }
        }
    }

    private async Task<bool> RunPythonScript(string workingDir, string scriptName, string args)
    {
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = "python3",
                Arguments = $"{scriptName} {args}",
                WorkingDirectory = workingDir,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            using var process = Process.Start(psi);
            if (process == null)
            {
                _logger.LogError("Failed to start python3 process for {Script}", scriptName);
                return false;
            }

            var output = await process.StandardOutput.ReadToEndAsync();
            var error = await process.StandardError.ReadToEndAsync();

            await process.WaitForExitAsync();

            if (!string.IsNullOrWhiteSpace(output))
            {
                _logger.LogInformation("Python script output: {Output}", output);
            }

            if (!string.IsNullOrWhiteSpace(error))
            {
                _logger.LogWarning("Python script stderr: {Error}", error);
            }

            return process.ExitCode == 0;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error running Python script {Script}", scriptName);
            return false;
        }
    }
}

public class UpdateResult
{
    public string Message { get; set; } = string.Empty;
}
