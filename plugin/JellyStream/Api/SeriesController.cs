using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging;
using Newtonsoft.Json.Linq;

namespace Jellyfin.Plugin.JellyStream.Api;

[ApiController]
[Route("JellyStream/Series")]
public class SeriesController : ControllerBase
{
    private readonly ILogger<SeriesController> _logger;

    public SeriesController(ILogger<SeriesController> logger)
    {
        _logger = logger;
    }

    [HttpGet("Search")]
    public async Task<ActionResult<List<SeriesInfo>>> SearchSeries(
        [FromQuery] string site = "aniworld",
        [FromQuery] string query = "")
    {
        try
        {
            _logger.LogInformation("Searching for series: {Query} on {Site}", query, site);

            var psi = new ProcessStartInfo
            {
                FileName = "python3",
                Arguments = $"/opt/JellyStream/utils/manual_updater.py --plugin --site {site} --search \"{query}\"",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            using var process = Process.Start(psi);
            if (process == null)
            {
                return StatusCode(500, "Failed to start manual_updater.py");
            }

            var output = await process.StandardOutput.ReadToEndAsync();
            var error = await process.StandardError.ReadToEndAsync();

            await process.WaitForExitAsync();

            if (process.ExitCode != 0)
            {
                _logger.LogError("manual_updater.py exited with code {Code}: {Error}", process.ExitCode, error);
                return StatusCode(500, $"Search failed: {error}");
            }

            // Parse JSON output
            var result = JObject.Parse(output);
            if (result["success"]?.Value<bool>() != true)
            {
                var errorMsg = result["error"]?.ToString() ?? "Unknown error";
                return StatusCode(500, errorMsg);
            }

            var seriesList = new List<SeriesInfo>();
            var seriesArray = result["series"] as JArray;

            if (seriesArray != null)
            {
                foreach (var series in seriesArray)
                {
                    seriesList.Add(new SeriesInfo
                    {
                        Name = series["name"]?.ToString() ?? "",
                        JellyfinName = series["jellyfin_name"]?.ToString() ?? "",
                        Url = series["url"]?.ToString() ?? "",
                        Site = site,
                        SeasonCount = series["season_count"]?.Value<int>() ?? 0,
                        EpisodeCount = series["episode_count"]?.Value<int>() ?? 0
                    });
                }
            }

            _logger.LogInformation("Found {Count} series matching '{Query}'", seriesList.Count, query);

            return Ok(seriesList);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error searching series");
            return StatusCode(500, ex.Message);
        }
    }
}

public class SeriesInfo
{
    public string Name { get; set; } = string.Empty;
    public string JellyfinName { get; set; } = string.Empty;
    public string Url { get; set; } = string.Empty;
    public string Site { get; set; } = string.Empty;
    public int SeasonCount { get; set; }
    public int EpisodeCount { get; set; }
}
