using System;
using System.Threading.Tasks;
using Jellyfin.Plugin.JellyStream.Api;
using Newtonsoft.Json.Linq;

namespace Jellyfin.Plugin.JellyStream.Api;

public interface ISeriesUpdater
{
    Task<UpdateResult> UpdateSeries(JObject series);
}
