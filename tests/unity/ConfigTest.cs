using System;
using System.Collections.Generic;
using CubeageSDK.Models;

public static class ConfigTest
{
    static void Equal<T>(T actual, T expected)
    {
        if (!EqualityComparer<T>.Default.Equals(actual, expected))
            throw new Exception("Expected " + expected + ", got " + actual);
    }
    public static void Main()
    {
        var config = new SdkConfig(new Dictionary<string, string> {
            { "yes", "TrUe" }, { "one", "1" }, { "no", "false" },
            { "number", "42" }, { "invalid", "not a number" }
        });
        Equal(config.Get("missing", "fallback"), "fallback");
        Equal(config.GetBool("yes"), true);
        Equal(config.GetBool("one"), true);
        Equal(config.GetBool("no", true), false);
        Equal(config.GetBool("missing", true), true);
        Equal(config.GetInt("number"), 42);
        Equal(config.GetInt("invalid", 7), 7);
        config.SetValues(null);
        Equal(config.Get("yes", "cleared"), "cleared");
        Equal(new SdkConfig(null).GetInt("missing", 9), 9);
        Console.WriteLine("Unity SdkConfig consumer tests passed");
    }
}
