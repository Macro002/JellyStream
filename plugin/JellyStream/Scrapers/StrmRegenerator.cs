using System;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Newtonsoft.Json.Linq;

namespace Jellyfin.Plugin.JellyStream.Api;

public class StrmRegenerator
{
    private readonly string _apiBaseUrl;
    private readonly ILogger _logger;
    private readonly Func<string, Task>? _progressCallback;

    private static readonly string[] LanguagePriority = new[]
    {
        "Deutsch",
        "mit Untertitel Deutsch",
        "mit Untertitel Englisch",
        "Englisch",
        "mit deutschen Untertiteln"
    };

    public StrmRegenerator(string apiBaseUrl, ILogger logger, Func<string, Task>? progressCallback = null)
    {
        _apiBaseUrl = apiBaseUrl;
        _logger = logger;
        _progressCallback = progressCallback;
    }

    public async Task<int> RegenerateSeries(JObject series, string jellyfinBasePath)
    {
        var seriesName = series["jellyfin_name"]?.ToString() ?? series["name"]?.ToString() ?? "Unknown";
        var safeName = SanitizeFilename(seriesName);

        var seriesDir = Path.Combine(jellyfinBasePath, safeName);

        // Remove old directory
        if (Directory.Exists(seriesDir))
        {
            Directory.Delete(seriesDir, true);
        }

        // Create series directory
        Directory.CreateDirectory(seriesDir);

        var strmCount = 0;
        var seasons = series["seasons"] as JObject;

        if (seasons == null)
        {
            return strmCount;
        }

        var totalEpisodes = seasons.Properties().Sum(s =>
        {
            var seasonData = s.Value as JObject;
            var episodes = seasonData?["episodes"] as JObject;
            return episodes?.Count ?? 0;
        });

        var currentEpisode = 0;

        foreach (var season in seasons)
        {
            var seasonNum = season.Key.Replace("season_", "");
            var seasonData = season.Value as JObject;
            var episodes = seasonData?["episodes"] as JObject;

            if (episodes == null) continue;

            var seasonDir = Path.Combine(seriesDir, $"Season {seasonNum.PadLeft(2, '0')}");
            Directory.CreateDirectory(seasonDir);

            foreach (var episode in episodes)
            {
                currentEpisode++;
                var episodeNum = episode.Key.Replace("episode_", "");

                if (_progressCallback != null)
                {
                    await _progressCallback($"Creating .strm file {currentEpisode}/{totalEpisodes}: Season {seasonNum} Episode {episodeNum}");
                }
                var episodeData = episode.Value as JObject;

                if (episodeData == null) continue;

                var totalStreams = episodeData["total_streams"]?.Value<int>() ?? 0;
                if (totalStreams == 0) continue;

                var redirectId = GetBestRedirect(episodeData);
                if (string.IsNullOrEmpty(redirectId)) continue;

                var strmPath = Path.Combine(seasonDir,
                    $"S{seasonNum.PadLeft(2, '0')}E{episodeNum.PadLeft(2, '0')}.strm");

                await File.WriteAllTextAsync(strmPath, $"{_apiBaseUrl}/{redirectId}");
                strmCount++;
            }
        }

        _logger.LogInformation("Regenerated {Count} .strm files for {Series}", strmCount, seriesName);
        return strmCount;
    }

    private string? GetBestRedirect(JObject episodeData)
    {
        var streamsByLanguage = episodeData["streams_by_language"] as JObject;
        if (streamsByLanguage == null) return null;

        // Try languages in priority order
        foreach (var language in LanguagePriority)
        {
            var languageStreams = streamsByLanguage[language] as JArray;
            if (languageStreams == null || languageStreams.Count == 0)
                continue;

            // Try providers in order
            foreach (var provider in new[] { "VOE", "Vidoza", "Doodstream" })
            {
                foreach (var stream in languageStreams)
                {
                    var streamObj = stream as JObject;
                    if (streamObj == null) continue;

                    var hoster = streamObj["hoster"]?.ToString() ?? streamObj["provider"]?.ToString();
                    if (hoster == provider)
                    {
                        var streamUrl = streamObj["stream_url"]?.ToString();
                        if (!string.IsNullOrEmpty(streamUrl) && streamUrl.Contains("/redirect/"))
                        {
                            return streamUrl.Split("/redirect/").Last();
                        }
                    }
                }
            }

            // If no preferred provider, use any redirect from this language
            foreach (var stream in languageStreams)
            {
                var streamObj = stream as JObject;
                if (streamObj == null) continue;

                var streamUrl = streamObj["stream_url"]?.ToString();
                if (!string.IsNullOrEmpty(streamUrl) && streamUrl.Contains("/redirect/"))
                {
                    return streamUrl.Split("/redirect/").Last();
                }
            }
        }

        return null;
    }

    private static string SanitizeFilename(string filename)
    {
        var invalid = new string(Path.GetInvalidFileNameChars()) + new string(Path.GetInvalidPathChars());
        var regex = new Regex($"[{Regex.Escape(invalid)}]");
        var sanitized = regex.Replace(filename, "").Trim(' ', '.');

        if (string.IsNullOrEmpty(sanitized))
        {
            return "unnamed";
        }

        return sanitized.Substring(0, Math.Min(200, sanitized.Length));
    }
}
