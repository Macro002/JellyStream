using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using HtmlAgilityPack;
using Microsoft.AspNetCore.Authorization;
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
    private readonly IHttpClientFactory _httpClientFactory;

    public UpdateController(ILogger<UpdateController> logger, IHttpClientFactory httpClientFactory)
    {
        _logger = logger;
        _httpClientFactory = httpClientFactory;
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
                    _logger.LogInformation("Background task: Loading database for {Name}", name);

                    // Load database
                    var json = await System.IO.File.ReadAllTextAsync(dataPath);
                    var data = JObject.Parse(json);
                    var seriesArray = data["series"] as JArray;

                    if (seriesArray == null)
                    {
                        _logger.LogError("Background task: No series found in database");
                        return;
                    }

                    // Find the series
                    JObject? targetSeries = null;
                    foreach (var series in seriesArray)
                    {
                        var seriesName = series["jellyfin_name"]?.ToString() ?? series["name"]?.ToString();
                        if (seriesName == name)
                        {
                            targetSeries = series as JObject;
                            break;
                        }
                    }

                    if (targetSeries == null)
                    {
                        _logger.LogError("Background task: Series not found: {Name}", name);
                        return;
                    }

                    _logger.LogInformation("Background task: Scraping episodes for {Name}", name);

                    // Update the series
                    ISeriesUpdater updater = site.ToLower() == "aniworld"
                        ? new AniworldUpdater(_httpClientFactory, _logger)
                        : new SerienstreamUpdater(_httpClientFactory, _logger);

                    var result = await updater.UpdateSeries(targetSeries);

                    _logger.LogInformation("Background task: Saving database for {Name}", name);

                    // Save database
                    var backupPath = dataPath + ".backup";
                    if (System.IO.File.Exists(backupPath))
                    {
                        System.IO.File.Delete(backupPath);
                    }
                    System.IO.File.Copy(dataPath, backupPath);

                    await System.IO.File.WriteAllTextAsync(dataPath, data.ToString(Formatting.Indented));

                    _logger.LogInformation("Background task: Generating .strm files for {Name}", name);

                    // Regenerate .strm files
                    var regenerator = new StrmRegenerator(config.ApiBaseUrl, _logger);
                    var strmCount = await regenerator.RegenerateSeries(targetSeries, jellyfinPath);

                    _logger.LogInformation("Background task complete for {Name}: {Episodes} episodes updated, {Strm} .strm files created",
                        name, result.EpisodesUpdated, strmCount);
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
}

public class UpdateResult
{
    public int EpisodesUpdated { get; set; }
    public int EpisodesFailed { get; set; }
    public int StrmFilesCreated { get; set; }
    public string Message { get; set; } = string.Empty;
}
