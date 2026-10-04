using System;

namespace UrbanFlowLauncher
{
    /// <summary>
    /// Minimal Windows Local-Mode permission shim used by Spark's bundled
    /// Hadoop file API. It starts no service, performs no network access and
    /// does not provide HDFS/YARN functionality. NTFS permissions are already
    /// managed by Windows for this single-user portable application.
    /// </summary>
    internal static class WinUtilsShim
    {
        public static int Main(string[] args)
        {
            if (args.Length == 0)
            {
                return 0;
            }

            var command = args[0].ToLowerInvariant();
            if (command == "groups")
            {
                Console.WriteLine(Environment.UserName);
            }
            return 0;
        }
    }
}

