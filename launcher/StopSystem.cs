using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace UrbanFlowLauncher
{
    internal static class StopProgram
    {
        private static void Notify(string message, MessageBoxIcon icon)
        {
            if (Environment.GetEnvironmentVariable("URBAN_FLOW_SILENT") == "1") return;
            MessageBox.Show(message, "关闭系统", MessageBoxButtons.OK, icon);
        }

        private static void StopLauncherWindow(string appHome)
        {
            string expected = Path.GetFullPath(Path.Combine(appHome, "启动系统.exe"));
            foreach (Process process in Process.GetProcessesByName("启动系统"))
            {
                try
                {
                    string actual = Path.GetFullPath(process.MainModule.FileName);
                    if (expected.Equals(actual, StringComparison.OrdinalIgnoreCase)) process.Kill();
                }
                catch { }
            }
        }

        [STAThread]
        private static void Main()
        {
            string appHome = Path.GetFullPath(AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar));
            string pidPath = Path.Combine(appHome, "work", "server.pid");
            string portPath = Path.Combine(appHome, "work", "server.port");
            if (!File.Exists(pidPath)) { StopLauncherWindow(appHome); Notify("系统当前未运行。", MessageBoxIcon.Information); return; }
            try
            {
                int pid = int.Parse(File.ReadAllText(pidPath));
                Process target = Process.GetProcessById(pid);
                string expected = Path.GetFullPath(Path.Combine(appHome, "runtime", "python", "python.exe"));
                string actual = Path.GetFullPath(target.MainModule.FileName);
                if (!expected.Equals(actual, StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("PID 对应的进程不是本系统，已拒绝关闭。 ");
                string taskkill = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "taskkill.exe");
                ProcessStartInfo info = new ProcessStartInfo(taskkill, "/PID " + pid + " /T /F"); info.CreateNoWindow = true; info.UseShellExecute = false;
                using (Process killer = Process.Start(info)) { if (killer != null) killer.WaitForExit(12000); }
                File.Delete(pidPath); if (File.Exists(portPath)) File.Delete(portPath);
                StopLauncherWindow(appHome);
                Notify("系统及 Spark 子进程已安全关闭。", MessageBoxIcon.Information);
            }
            catch (ArgumentException)
            {
                File.Delete(pidPath); if (File.Exists(portPath)) File.Delete(portPath);
                StopLauncherWindow(appHome);
                Notify("未发现运行中的系统进程，状态文件已清理。", MessageBoxIcon.Information);
            }
            catch (Exception ex) { Notify("关闭失败：" + ex.Message, MessageBoxIcon.Error); }
        }
    }
}
