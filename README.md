# 基于 Spark 的城市出行客流数据分析系统

面向本科毕业设计答辩与功能验证的绿色离线 Web 系统。系统围绕统一的虚拟城市交通数据底座，完成数据导入与清洗、Spark SQL 离线分析、Structured Streaming 实时计算、OD 流向、客流预测、容量预警和决策报告。

> 本绿色离线版本采用 Apache Spark Local Mode 作为 Spark 执行环境，以降低毕业设计部署和演示复杂度。

## 重要数据说明

当前系统使用内置模拟城市交通数据集进行功能验证，通过本地 GeoJSON、虚拟站点及线路数据完成客流分析、OD 流向、预测与预警。实际应用时可通过替换城市 GeoJSON、站点、线路和真实客流数据迁移到实际城市环境。

“星海示例市”完全属于虚拟示例城市，不代表任何真实城市交通状况。基础目录固定包含 8 个区域、40 个站点和 12 条线路；SQLite、CSV、JSON、XLSX、Parquet、Spark SQL、实时流、模型、地图和预警均引用同一组实体、坐标与容量。

## 技术架构

- 前端：Vue 3、Vite、Element Plus、ECharts、Pinia、Vue Router、Axios。
- 后端：FastAPI、Uvicorn、SQLAlchemy、Pydantic、SQLite。
- 数据计算：PySpark 3.5 Local Mode、Spark SQL、DataFrame、Structured Streaming、Parquet + Snappy。
- 模型：statsmodels ARIMA、Spark MLlib RandomForestRegressor、Spark MLlib GBTRegressor。
- 测试：pytest、Playwright、Vite production build。
- 地图：ECharts `registerMap()` 加载 `assets/maps/demo_city.json`，不调用任何在线地图 API。

数据流：

```text
固定城市目录 + Demo CSV/JSON/XLSX
                ↓
       Spark DataFrame 清洗
                ↓
   本地 Parquet（按日期、交通类型分区）
        ↓              ↓
 Spark SQL/OD     Structured Streaming
        ↓              ↓
     ARIMA / Random Forest / GBT
                ↓
      容量负载率、预警、决策报告
```

本项目的 Parquet 是本地文件存储，不是 HDFS；系统也不包含或依赖 Hadoop/HDFS/YARN 服务。

## 绿色版使用方法

1. 将整个 `城市出行客流数据分析系统` 文件夹解压到任意本地目录，目录可以包含中文和空格。
2. 双击 `启动系统.exe`。
3. 等待状态窗口显示 Web 服务正常，默认浏览器会自动打开。
4. 使用下方任一演示账号登录。
5. 使用结束后双击 `关闭系统.exe`，它会同时关闭 FastAPI 与 Spark 子进程。

绿色版自带 `runtime/python` 与 `runtime/java`，不依赖系统 Python、Java、Node.js、数据库或开发工具。服务只绑定 `127.0.0.1`，正常运行期间不访问外部 API。

## 默认账号

| 角色 | 用户名 | 密码 | 主要权限 |
|---|---|---|---|
| 系统管理员 | `admin` | `admin123` | 全部功能、用户、日志和配置 |
| 数据分析员 | `analyst` | `analyst123` | 数据、分析、模型、实时流和预警 |
| 只读访客 | `viewer` | `viewer123` | 看板、统计、预测结果和报告查看 |

权限由 FastAPI 后端 RBAC 强制校验，不能依靠隐藏前端菜单绕过。

## 功能模块

- 综合态势：核心指标、小时曲线、出行方式、站点排行以及区域热力、站点分布、Top-N OD 三种离线地图模式。
- 数据管理：CSV/JSON/XLSX 上传与预览、Spark 清洗任务、实体引用校验、Parquet 存储统计、恢复演示数据。
- Spark 分析：日/周/月、小时与高峰、区域、站点、线路、交通方式、OD 排行和 OD 矩阵。
- 实时客流：固定目录模拟源、5/10/15 分钟事件时间窗口、站点/线路/区域实时聚合、暂停/继续/停止/重置。
- 客流预测：真实训练 ARIMA、Random Forest 和 GBT，展示 MAE、RMSE、R²及时间有序测试集曲线。
- 预警与决策：按 `当前或预测客流 / capacity` 计算负载率，统一黄色、橙色、红色预警与针对性建议。
- 报告中心：生成并下载完全离线的 HTML 决策分析报告。
- 系统管理：用户与角色、操作日志、阈值配置、Web/SQLite/Spark/模型/数据目录健康检查。

## 项目目录

```text
backend/                  FastAPI、SQLite、RBAC 与业务服务
frontend/                 Vue 3 源码、Playwright 与 production dist
spark_jobs/               预处理、批处理和 ML 作业
assets/maps/              固定虚拟城市 GeoJSON
config/                   系统配置与固定城市目录
data/demo/                60,000 行 CSV/JSON/XLSX Demo
data/parquet/             本地 Snappy Parquet 分区
data/database/            SQLite 数据库
models/                   预训练模型
runtime/python/           便携 Python 3.11 与全部依赖
runtime/java/             便携 x64 JRE 17
launcher/                 Windows 启动器/关闭器源码
scripts/build_release.py  一键 Release 构建脚本
tests/                    pytest 单元、API 与 Spark 集成测试
docs/                     设计与开发状态文档
```

## 开发启动

后端（项目根目录）：

```powershell
$env:JAVA_HOME="$PWD\runtime\java"
& .\runtime\python\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8765 --reload
```

前端（需要开发用 Node.js/pnpm；最终绿色版不需要）：

```powershell
cd frontend
pnpm install
pnpm dev
```

访问 `http://127.0.0.1:5173`。前端开发服务器会把 `/api` 代理到 8765。

## 测试

```powershell
& .\runtime\python\python.exe -m pytest tests -q
cd frontend
pnpm run build
pnpm run e2e
```

Playwright 测试真实点击登录、菜单、上传、Spark 清洗、Spark 分析、Structured Streaming、模型训练、预警、日志和用户管理，并使用本机 Microsoft Edge 作为 Chromium 浏览器。

## Release 构建

项目根目录执行一条命令：

```powershell
& .\runtime\python\python.exe .\scripts\build_release.py
```

脚本会构建 Vue、编译 x64 WinForms 启停器、复制应用与便携运行时、筛选干净 Demo 状态、生成预警/报告/版本信息并扫描外部 CDN/API。输出目录为：

```text
release/城市出行客流数据分析系统/
```

## 数据迁移说明

迁移到真实城市环境时，需要同步替换：

1. `assets/maps/demo_city.json` 行政区域边界；
2. `config/demo_city_catalog.json` 的区域、站点、坐标、容量和线路关系；
3. 客流源数据中的实体 ID；
4. 重新执行 Spark 清洗、分析和模型训练。

不得只替换地图而保留不匹配的站点、线路或容量，否则系统会在清洗阶段将记录识别为无效引用。

## 常见问题

- 启动器提示运行环境缺失：确认解压完整，`runtime/python/python.exe` 与 `runtime/java/bin/java.exe` 均存在。
- 默认端口被占用：启动器会自动在 `8765-8795` 中选择可用端口。
- Spark 首次启动较慢：第一次初始化 JVM 通常比页面切换慢，状态窗口会持续显示进度。
- 页面无法访问：查看 `logs/system.log`，然后用 `关闭系统.exe` 清理进程后重试。
- 数据目录不可写：请把项目放在当前用户拥有写权限的本地目录，不要直接放到受保护的系统目录。
- 地图没有底图：确认 `assets/maps/demo_city.json` 未被删除；系统不使用高德、百度或 Google 地图。
- 想恢复初始数据：管理员或分析员可在“数据管理”点击“恢复演示数据”。

## 离线与安全边界

- Web 服务仅监听 `127.0.0.1`，不监听公网地址。
- 前端构建不包含 CDN、在线字体或在线地图链接。
- 口令使用 PBKDF2 加盐哈希保存；Bearer 登录令牌由本地服务签发。
- 上传文件名会被净化并存入项目数据目录；报告下载限制在 `data/result`。
- `关闭系统.exe` 会校验 PID 对应程序路径后再关闭完整进程树，避免误杀其他 Python 程序。
