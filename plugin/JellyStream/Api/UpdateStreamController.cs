using System;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Jellyfin.Plugin.JellyStream.Api;

[ApiController]
[Route("JellyStream/UpdateStream")]
public class UpdateStreamController : ControllerBase
{
    private readonly ILogger<UpdateStreamController> _logger;
    private readonly IHttpClientFactory _httpClientFactory;

    public UpdateStreamController(ILogger<UpdateStreamController> logger, IHttpClientFactory httpClientFactory)
    {
        _logger = logger;
        _httpClientFactory = httpClientFactory;
    }

    [HttpGet("Series")]
    public async Task UpdateSeriesStream(
        [FromQuery] string name,
        [FromQuery] string site = "aniworld")
    {
        Response.Headers.Add("Content-Type", "text/event-stream");
        Response.Headers.Add("Cache-Control", "no-cache");
        Response.Headers.Add("Connection", "keep-alive");

        async Task SendEvent(string eventData)
        {
            var data = $"data: {eventData}\n\n";
            await Response.Body.WriteAsync(Encoding.UTF8.GetBytes(data));
            await Response.Body.FlushAsync();
        }

        try
        {
            var config = Plugin.Instance?.Configuration;
            if (config == null)
            {
                await SendEvent(JsonConvert.SerializeObject(new { error = "Plugin not configured" }));
                return;
            }

            string dataPath = site.ToLower() == "aniworld"
                ? config.AniworldDataPath
                : config.SerienstreamDataPath;

            string jellyfinPath = site.ToLower() == "aniworld"
                ? config.AniworldJellyfinPath
                : config.SerienstreamJellyfinPath;

            if (!System.IO.File.Exists(dataPath))
            {
                await SendEvent(JsonConvert.SerializeObject(new { error = $"Database file not found: {dataPath}" }));
                return;
            }

            await SendEvent(JsonConvert.SerializeObject(new { status = "loading", message = "Loading series database..." }));

            var json = await System.IO.File.ReadAllTextAsync(dataPath);
            var data = JObject.Parse(json);
            var seriesArray = data["series"] as JArray;

            if (seriesArray == null)
            {
                await SendEvent(JsonConvert.SerializeObject(new { error = "No series found in database" }));
                return;
            }

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
                await SendEvent(JsonConvert.SerializeObject(new { error = $"Series not found: {name}" }));
                return;
            }

            await SendEvent(JsonConvert.SerializeObject(new { status = "scraping", message = "Starting episode scraping..." }));

            ISeriesUpdater updater = site.ToLower() == "aniworld"
                ? new AniworldUpdater(_httpClientFactory, _logger, async (msg) => await SendEvent(JsonConvert.SerializeObject(new { status = "scraping", message = msg })))
                : new SerienstreamUpdater(_httpClientFactory, _logger, async (msg) => await SendEvent(JsonConvert.SerializeObject(new { status = "scraping", message = msg })));

            var result = await updater.UpdateSeries(targetSeries);

            await SendEvent(JsonConvert.SerializeObject(new { status = "saving", message = "Saving database..." }));

            var backupPath = dataPath + ".backup";
            if (System.IO.File.Exists(backupPath))
            {
                System.IO.File.Delete(backupPath);
            }
            System.IO.File.Copy(dataPath, backupPath);
            await System.IO.File.WriteAllTextAsync(dataPath, data.ToString(Formatting.Indented));

            await SendEvent(JsonConvert.SerializeObject(new { status = "generating", message = "Generating .strm files..." }));

            var regenerator = new StrmRegenerator(config.ApiBaseUrl, _logger, async (msg) => await SendEvent(JsonConvert.SerializeObject(new { status = "generating", message = msg })));
            var strmCount = await regenerator.RegenerateSeries(targetSeries, jellyfinPath);

            result.StrmFilesCreated = strmCount;

            await SendEvent(JsonConvert.SerializeObject(new
            {
                status = "complete",
                episodesUpdated = result.EpisodesUpdated,
                episodesFailed = result.EpisodesFailed,
                strmFilesCreated = strmCount,
                message = $"Complete! Updated {result.EpisodesUpdated} episodes, created {strmCount} .strm files"
            }));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error updating series");
            await SendEvent(JsonConvert.SerializeObject(new { error = ex.Message }));
        }
    }
}
