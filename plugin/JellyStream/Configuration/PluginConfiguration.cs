using MediaBrowser.Model.Plugins;

namespace Jellyfin.Plugin.JellyStream.Configuration;

public class PluginConfiguration : BasePluginConfiguration
{
    public string ScriptPath { get; set; } = "/opt/JellyStream/utils/manual_updater.py";
}
