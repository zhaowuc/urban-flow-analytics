from __future__ import annotations

import html
from datetime import datetime

from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.database.session import SessionLocal
from backend.app.models.entities import DecisionRecord, Station, Warning
from backend.app.services.analysis import latest_analysis
from backend.app.services.predictions import latest_model_comparison


def generate_decision_report() -> tuple[str, str]:
    _, analysis = latest_analysis()
    with SessionLocal() as db:
        warnings = db.scalars(select(Warning).where(Warning.status == "active").order_by(Warning.load_rate.desc())).all()
        decisions = db.scalars(select(DecisionRecord).order_by(DecisionRecord.created_at.desc()).limit(20)).all()
        stations = {item.code: item.name for item in db.scalars(select(Station)).all()}
    summary = analysis["summary"]
    regions = analysis["regions"][:5]
    station_rows = analysis["stations_top10"][:5]
    model_rows = latest_model_comparison()
    generated = datetime.now()

    def rows(items: list[dict], columns: list[tuple[str, str]]) -> str:
        return "".join(
            "<tr>" + "".join(f"<td>{html.escape(str(item.get(key, '—')))}</td>" for key, _ in columns) + "</tr>"
            for item in items
        )

    report = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>城市客流决策报告</title>
<style>body{{font-family:'Microsoft YaHei UI',sans-serif;color:#142033;margin:40px;line-height:1.65}}h1{{color:#0B1F3A}}h2{{margin-top:28px;color:#1769E0;border-bottom:1px solid #dce5f0;padding-bottom:8px}}.meta{{color:#5e6b7c}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}.card{{background:#f3f6fa;border-radius:10px;padding:16px}}.value{{font-size:25px;font-weight:700}}table{{width:100%;border-collapse:collapse;margin-top:10px}}th,td{{padding:10px;border-bottom:1px solid #e2e8f0;text-align:left}}th{{background:#edf4ff}}.note{{background:#eef8f7;padding:14px;border-left:4px solid #0ea5a8}}</style></head>
<body><h1>星海示例市客流分析与调度决策报告</h1>
<p class="meta">生成时间：{generated:%Y-%m-%d %H:%M:%S}　|　计算模式：Spark Local 离线部署模式</p>
<p class="note">本报告基于系统内置虚拟示例城市交通数据集生成，不代表任何真实城市运行情况。</p>
<h2>一、当前总体客流</h2><div class="cards">
<div class="card">今日总客流<div class="value">{summary['today_total']:,}</div></div>
<div class="card">当前小时客流<div class="value">{summary['current_flow']:,}</div></div>
<div class="card">较昨日变化<div class="value">{summary['yesterday_change_percent']:.2f}%</div></div></div>
<h2>二、高峰与热点区域</h2><table><thead><tr><th>区域</th><th>客流量</th><th>平均客流</th></tr></thead><tbody>{rows(regions, [('region_id','区域'),('passenger_flow','客流量'),('average_flow','平均客流')])}</tbody></table>
<h2>三、热门站点</h2><table><thead><tr><th>站点</th><th>客流量</th><th>平均客流</th></tr></thead><tbody>{rows([{**item,'station_id':stations.get(item['station_id'],item['station_id'])} for item in station_rows], [('station_id','站点'),('passenger_flow','客流量'),('average_flow','平均客流')])}</tbody></table>
<h2>四、模型预测</h2><table><thead><tr><th>模型</th><th>MAE</th><th>RMSE</th><th>R²</th></tr></thead><tbody>{rows(model_rows, [('model_type','模型'),('mae','MAE'),('rmse','RMSE'),('r2','R²')])}</tbody></table>
<h2>五、风险预警</h2><p>当前有效预警 {len(warnings)} 条。</p><table><thead><tr><th>站点</th><th>等级</th><th>预测客流</th><th>容量</th><th>负载率</th></tr></thead><tbody>{rows([{'station':stations.get(w.station_code,w.station_code),'level':w.level,'predicted':round(w.predicted_flow,1),'capacity':int(w.capacity),'rate':f'{w.load_rate*100:.1f}%'} for w in warnings], [('station','站点'),('level','等级'),('predicted','预测客流'),('capacity','容量'),('rate','负载率')])}</tbody></table>
<h2>六、调度建议</h2><ol>{''.join(f'<li><strong>{html.escape(item.category)}</strong>：{html.escape(item.suggestion)}<br><span class="meta">{html.escape(item.rationale)}</span></li>' for item in decisions)}</ol>
</body></html>"""
    filename = f"decision_report_{generated:%Y%m%d_%H%M%S}.html"
    path = settings.app_home / "data" / "result" / filename
    path.write_text(report, encoding="utf-8")
    return str(path.relative_to(settings.app_home)), report

