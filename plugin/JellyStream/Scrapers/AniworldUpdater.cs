using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Threading.Tasks;
using HtmlAgilityPack;
using Jellyfin.Plugin.JellyStream.Api;
using Microsoft.Extensions.Logging;
using Newtonsoft.Json.Linq;

namespace Jellyfin.Plugin.JellyStream.Api;

public class AniworldUpdater : ISeriesUpdater
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly ILogger _logger;
    private readonly Func<string, Task>? _progressCallback;
    private const string UserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36";

    private static readonly string[] LanguagePriority = new[]
    {
        "Deutsch",
        "mit Untertitel Deutsch",
        "mit Untertitel Englisch"
    };

    public AniworldUpdater(IHttpClientFactory httpClientFactory, ILogger logger, Func<string, Task>? progressCallback = null)
    {
        _httpClientFactory = httpClientFactory;
        _logger = logger;
        _progressCallback = progressCallback;
    }

    public async Task<UpdateResult> UpdateSeries(JObject series)
    {
        var result = new UpdateResult();
        var seasons = series["seasons"] as JObject;

        if (seasons == null)
        {
            return result;
        }

        var totalEpisodes = seasons.Properties().Sum(s =>
        {
            var seasonData = s.Value as JObject;
            var episodes = seasonData?["episodes"] as JObject;
            return episodes?.Count ?? 0;
        });

        var httpClient = _httpClientFactory.CreateClient();
        httpClient.DefaultRequestHeaders.Add("User-Agent", UserAgent);

        var currentEpisode = 0;

        foreach (var season in seasons)
        {
            var seasonData = season.Value as JObject;
            var episodes = seasonData?["episodes"] as JObject;

            if (episodes == null) continue;

            foreach (var episode in episodes)
            {
                var episodeData = episode.Value as JObject;
                if (episodeData == null) continue;

                var episodeUrl = episodeData["url"]?.ToString();
                if (string.IsNullOrEmpty(episodeUrl))
                {
                    continue;
                }

                currentEpisode++;

                try
                {
                    _logger.LogDebug("Scraping episode: {Url}", episodeUrl);

                    if (_progressCallback != null)
                    {
                        await _progressCallback($"Scraping episode {currentEpisode}/{totalEpisodes}: {season.Key} Episode {episode.Key}");
                    }

                    var response = await httpClient.GetStringAsync(episodeUrl);
                    var doc = new HtmlDocument();
                    doc.LoadHtml(response);

                    // Extract language mappings
                    var languages = new Dictionary<string, string>();
                    var langBox = doc.DocumentNode.SelectSingleNode("//div[@class='changeLanguageBox']");

                    if (langBox != null)
                    {
                        var langElements = langBox.SelectNodes(".//*[@data-lang-key and @title]");
                        if (langElements != null)
                        {
                            foreach (var element in langElements)
                            {
                                var langKey = element.GetAttributeValue("data-lang-key", "");
                                var langTitle = element.GetAttributeValue("title", "");
                                if (!string.IsNullOrEmpty(langKey) && !string.IsNullOrEmpty(langTitle))
                                {
                                    languages[langKey] = langTitle;
                                }
                            }
                        }
                    }

                    // Extract streams
                    var streamsByLanguage = new JObject();
                    var videoSection = doc.DocumentNode.SelectSingleNode("//div[@class='hosterSiteVideo']");

                    if (videoSection != null)
                    {
                        var rowUl = videoSection.SelectSingleNode(".//ul[@class='row']");
                        if (rowUl != null)
                        {
                            var streamItems = rowUl.SelectNodes(".//li[@data-lang-key and @data-link-target]");
                            if (streamItems != null)
                            {
                                foreach (var item in streamItems)
                                {
                                    var langKey = item.GetAttributeValue("data-lang-key", "");
                                    var linkTarget = item.GetAttributeValue("data-link-target", "");

                                    if (string.IsNullOrEmpty(langKey) || string.IsNullOrEmpty(linkTarget))
                                    {
                                        continue;
                                    }

                                    var language = languages.ContainsKey(langKey)
                                        ? languages[langKey]
                                        : $"Unknown_{langKey}";

                                    var h4Element = item.SelectSingleNode(".//h4");
                                    var hoster = h4Element?.InnerText.Trim() ?? "Unknown";

                                    var streamUrl = linkTarget.StartsWith("http")
                                        ? linkTarget
                                        : $"https://aniworld.to{linkTarget}";

                                    if (streamsByLanguage[language] == null)
                                    {
                                        streamsByLanguage[language] = new JArray();
                                    }

                                    ((JArray)streamsByLanguage[language]!).Add(new JObject
                                    {
                                        ["hoster"] = hoster,
                                        ["stream_url"] = streamUrl
                                    });
                                }
                            }
                        }
                    }

                    var totalStreams = streamsByLanguage.Properties()
                        .Sum(p => ((JArray)p.Value).Count);

                    episodeData["streams_by_language"] = streamsByLanguage;
                    episodeData["total_streams"] = totalStreams;

                    result.EpisodesUpdated++;

                    await Task.Delay(2000); // Be nice to the server
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error scraping episode: {Url}", episodeUrl);
                    result.EpisodesFailed++;
                }
            }
        }

        result.Message = $"Updated {result.EpisodesUpdated} episodes";
        return result;
    }
}
