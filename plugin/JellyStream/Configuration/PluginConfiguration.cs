using MediaBrowser.Model.Plugins;

namespace Jellyfin.Plugin.JellyStream.Configuration;

public class PluginConfiguration : BasePluginConfiguration
{
    public string AniworldDataPath { get; set; } = "/opt/JellyStream/sites/aniworld/data/final_series_data.json";

    public string SerienstreamDataPath { get; set; } = "/opt/JellyStream/sites/serienstream/data/final_series_data.json";

    public string AniworldJellyfinPath { get; set; } = "/media/jellyfin/aniworld";

    public string SerienstreamJellyfinPath { get; set; } = "/media/jellyfin/serienstream";

    public string ApiBaseUrl { get; set; } = "http://localhost:3000/stream/redirect";
}
