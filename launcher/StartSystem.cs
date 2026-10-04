using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace UrbanFlowLauncher
{
    internal sealed class StartWindow : Form
    {
        private readonly Label phase = new Label();
        private readonly Label pythonState = new Label();
        private readonly Label javaState = new Label();
        private readonly Label sqliteState = new Label();
        private readonly Label sparkState = new Label();
        private readonly Label webState = new Label();
        private readonly Button openButton = new Button();
        private string appHome = "";
        private int port = 8765;

        internal StartWindow()
        {
            Text = "城市出行客流数据分析系统";
            ClientSize = new Size(520, 430);
            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            BackColor = Color.FromArgb(245, 248, 252);
            Font = new Font("Microsoft YaHei UI", 9F);

            Panel header = new Panel { Dock = DockStyle.Top, Height = 104, BackColor = Color.FromArgb(12, 31, 54) };
            Label title = new Label { Text = "城市出行客流数据分析系统", ForeColor = Color.White, Font = new Font("Microsoft YaHei UI", 16F, FontStyle.Bold), AutoSize = true, Location = new Point(28, 24) };
            Label sub = new Label { Text = "SPARK LOCAL · OFFLINE ANALYTICS", ForeColor = Color.FromArgb(112, 155, 202), Font = new Font("Segoe UI", 8F, FontStyle.Bold), AutoSize = true, Location = new Point(30, 63) };
            header.Controls.Add(title); header.Controls.Add(sub); Controls.Add(header);

            phase.Text = "正在检查运行环境..."; phase.ForeColor = Color.FromArgb(42, 61, 83); phase.Font = new Font("Microsoft YaHei UI", 10F, FontStyle.Bold); phase.AutoSize = true; phase.Location = new Point(30, 126); Controls.Add(phase);
            AddStatusRow("Python Runtime", pythonState, 170);
            AddStatusRow("Java Runtime", javaState, 208);
            AddStatusRow("SQLite", sqliteState, 246);
            AddStatusRow("Spark", sparkState, 284);
            AddStatusRow("Web 服务", webState, 322);

            openButton.Text = "打开系统"; openButton.Enabled = false; openButton.Size = new Size(118, 38); openButton.Location = new Point(372, 370); openButton.FlatStyle = FlatStyle.Flat; openButton.FlatAppearance.BorderSize = 0; openButton.BackColor = Color.FromArgb(42, 105, 226); openButton.ForeColor = Color.White; openButton.Cursor = Cursors.Hand; openButton.Click += delegate { OpenBrowser(); }; Controls.Add(openButton);
            Shown += async delegate { await StartAsync(); };
        }

        private void AddStatusRow(string name, Label state, int y)
        {
            Label label = new Label { Text = name, AutoSize = true, Location = new Point(32, y), ForeColor = Color.FromArgb(83, 101, 124) };
            state.Text = "等待检查"; state.TextAlign = ContentAlignment.MiddleRight; state.Size = new Size(210, 24); state.Location = new Point(280, y - 5); state.ForeColor = Color.FromArgb(142, 154, 170);
            Controls.Add(label); Controls.Add(state);
        }

        private void SetState(Label label, string text, bool ok)
        {
            label.Text = text;
            label.ForeColor = ok ? Color.FromArgb(18, 150, 102) : Color.FromArgb(218, 65, 72);
        }

        private async Task StartAsync()
        {
            try
            {
                appHome = Path.GetFullPath(AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar));
                string python = Path.Combine(appHome, "runtime", "python", "python.exe");
                string java = Path.Combine(appHome, "runtime", "java", "bin", "java.exe");
                string appDirectory = Path.Combine(appHome, "app");
                SetState(pythonState, File.Exists(python) ? "正常" : "缺失", File.Exists(python));
                SetState(javaState, File.Exists(java) ? "正常" : "缺失", File.Exists(java));
                if (!File.Exists(python) || !File.Exists(java) || !Directory.Exists(appDirectory)) throw new InvalidOperationException("绿色运行环境不完整，请重新解压发行包。 ");

                foreach (string relative in new[] { "data\\database", "data\\upload", "data\\parquet", "data\\result", "data\\stream", "models", "logs", "work" }) Directory.CreateDirectory(Path.Combine(appHome, relative));
                SetState(sqliteState, File.Exists(Path.Combine(appHome, "data", "database", "system.db")) ? "正常" : "首次启动将自动初始化", true);

                int existingPort;
                if (TryGetExistingServer(out existingPort))
                {
                    port = existingPort;
                    SetState(sparkState, "正常", true); SetState(webState, "已运行", true);
                    phase.Text = "系统已经运行，正在打开浏览器..."; openButton.Enabled = true; OpenBrowser(); return;
                }

                port = FindAvailablePort(8765, 8795);
                ProcessStartInfo info = new ProcessStartInfo();
                info.FileName = python;
                info.Arguments = "-m uvicorn backend.app.main:app --host 127.0.0.1 --port " + port + " --log-level warning";
                info.WorkingDirectory = appDirectory;
                info.UseShellExecute = false;
                info.CreateNoWindow = true;
                info.EnvironmentVariables["URBAN_FLOW_HOME"] = appHome;
                info.EnvironmentVariables["JAVA_HOME"] = Path.Combine(appHome, "runtime", "java");
                info.EnvironmentVariables["PYSPARK_PYTHON"] = python;
                info.EnvironmentVariables["PYSPARK_DRIVER_PYTHON"] = python;
                info.EnvironmentVariables["SPARK_LOCAL_DIRS"] = Path.Combine(appHome, "work", "spark-local");
                info.EnvironmentVariables["HADOOP_HOME"] = Path.Combine(appHome, "runtime", "spark-winutils");
                info.EnvironmentVariables["SPARK_LOCAL_IP"] = "127.0.0.1";
                string binPath = Path.Combine(appHome, "runtime", "spark-winutils", "bin");
                info.EnvironmentVariables["PATH"] = binPath + Path.PathSeparator + info.EnvironmentVariables["PATH"];
                Process process = Process.Start(info);
                if (process == null) throw new InvalidOperationException("后端进程无法启动。 ");
                File.WriteAllText(Path.Combine(appHome, "work", "server.pid"), process.Id.ToString(), Encoding.ASCII);
                File.WriteAllText(Path.Combine(appHome, "work", "server.port"), port.ToString(), Encoding.ASCII);

                phase.Text = "正在启动 Web 服务与 Spark 引擎...";
                bool webReady = false; bool sparkReady = false;
                for (int i = 0; i < 90; i++)
                {
                    string json = await ReadHealthAsync();
                    webReady = json != null;
                    sparkReady = json != null && json.Replace(" ", "").Contains("\"spark\":{\"ok\":true");
                    if (webReady) SetState(webState, "正常 · 127.0.0.1:" + port, true);
                    if (sparkReady) { SetState(sparkState, "正常 · local[*]", true); break; }
                    await Task.Delay(700);
                }
                if (!webReady) throw new InvalidOperationException("Web 服务启动超时，请查看 logs/system.log。 ");
                if (!sparkReady) SetState(sparkState, "后台初始化中", true);
                SetState(sqliteState, "正常", true);
                phase.Text = "系统启动成功，正在打开浏览器...";
                openButton.Enabled = true;
                OpenBrowser();
            }
            catch (Exception ex)
            {
                phase.Text = "启动失败：" + ex.Message;
                phase.ForeColor = Color.FromArgb(198, 51, 58);
            }
        }

        private async Task<string> ReadHealthAsync()
        {
            try
            {
                HttpWebRequest request = (HttpWebRequest)WebRequest.Create("http://127.0.0.1:" + port + "/api/health");
                request.Timeout = 1300; request.ReadWriteTimeout = 1300;
                using (WebResponse response = await request.GetResponseAsync())
                using (StreamReader reader = new StreamReader(response.GetResponseStream(), Encoding.UTF8)) return await reader.ReadToEndAsync();
            }
            catch { return null; }
        }

        private bool TryGetExistingServer(out int existingPort)
        {
            existingPort = 0;
            try
            {
                string pidPath = Path.Combine(appHome, "work", "server.pid"); string portPath = Path.Combine(appHome, "work", "server.port");
                if (!File.Exists(pidPath) || !File.Exists(portPath)) return false;
                int pid = int.Parse(File.ReadAllText(pidPath)); existingPort = int.Parse(File.ReadAllText(portPath));
                Process process = Process.GetProcessById(pid);
                string expected = Path.GetFullPath(Path.Combine(appHome, "runtime", "python", "python.exe"));
                string actual = Path.GetFullPath(process.MainModule.FileName);
                return !process.HasExited && expected.Equals(actual, StringComparison.OrdinalIgnoreCase);
            }
            catch { return false; }
        }

        private static int FindAvailablePort(int first, int last)
        {
            for (int value = first; value <= last; value++)
            {
                TcpListener listener = null;
                try { listener = new TcpListener(IPAddress.Loopback, value); listener.Start(); return value; }
                catch (SocketException) { }
                finally { if (listener != null) listener.Stop(); }
            }
            throw new InvalidOperationException("本机端口 8765-8795 均被占用。 ");
        }

        private void OpenBrowser()
        {
            if (Environment.GetEnvironmentVariable("URBAN_FLOW_NO_BROWSER") == "1") return;
            try { Process.Start(new ProcessStartInfo("http://127.0.0.1:" + port + "/") { UseShellExecute = true }); }
            catch { phase.Text = "系统已启动，请访问 http://127.0.0.1:" + port; }
        }
    }

    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false); Application.Run(new StartWindow());
        }
    }
}
