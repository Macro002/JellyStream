using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging;
using Newtonsoft.Json;
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

    [HttpGet("List")]
    public async Task<ActionResult<List<SeriesInfo>>> GetSeriesList([FromQuery] string site = "aniworld")
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

            if (!System.IO.File.Exists(dataPath))
            {
                return NotFound($"Database file not found: {dataPath}");
            }

            var json = await System.IO.File.ReadAllTextAsync(dataPath);
            var data = JObject.Parse(json);
            var seriesArray = data["series"] as JArray;

            if (seriesArray == null)
            {
                return Ok(new List<SeriesInfo>());
            }

            var seriesList = new List<SeriesInfo>();

            foreach (var series in seriesArray)
            {
                var name = series["name"]?.ToString() ?? "Unknown";
                var jellyfinName = series["jellyfin_name"]?.ToString() ?? name;
                var url = series["url"]?.ToString() ?? "";

                var seasons = series["seasons"] as JObject;
                var seasonCount = seasons?.Count ?? 0;

                var totalEpisodes = 0;
                if (seasons != null)
                {
                    foreach (var season in seasons)
                    {
                        var seasonData = season.Value as JObject;
                        var episodes = seasonData?["episodes"] as JObject;
                        totalEpisodes += episodes?.Count ?? 0;
                    }
                }

                seriesList.Add(new SeriesInfo
                {
                    Name = name,
                    JellyfinName = jellyfinName,
                    Url = url,
                    Site = site,
                    SeasonCount = seasonCount,
                    EpisodeCount = totalEpisodes
                });
            }

            return Ok(seriesList.OrderBy(s => s.Name).ToList());
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error loading series list");
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
