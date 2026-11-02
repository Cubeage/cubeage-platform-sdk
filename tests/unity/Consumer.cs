using System;
using System.Collections.Generic;
using CubeageSDK.Models;
using CubeageSDK.Editor;

public static class Consumer
{
    // Compile the public package surface from a separate assembly, not its sources.
    public static void CompileOnly()
    {
        var sdk = CubeageSDK.CubeageSDK.Instance;
        sdk.Init(config => config.Get("key"), error => { });
        sdk.TrackEvent("consumer_compile", new Dictionary<string, object>());
        sdk.TrackPurchase("product", 1, "USD", "transaction", "receipt");
        sdk.StartSession(id => { });
        sdk.EndSession(seconds => { });
        sdk.TrackAttribution((id, first) => { });
        sdk.TrackAdRevenue(new AdImpressionData());
        sdk.SetUserProperty("key", "value");
        sdk.SetUserProperties(new Dictionary<string, string>());
        sdk.CheckForUpdate(update => { }, error => { });
        string text = sdk.GetConfig("key");
        bool flag = sdk.GetConfigBool("key");
        int number = sdk.GetConfigInt("key");
        CubeageSDKSettings settings = CubeageSDKSettings.Load();
        GC.KeepAlive(new object[] { text, flag, number, settings });
    }
}
