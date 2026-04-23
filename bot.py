# -*- coding: utf-8 -*-
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta, timezone
import requests
import os

class StockBot:
    def __init__(self):
        self.webhook = os.getenv("WECHAT_WEBHOOK_URL")
        self.tz = timezone(timedelta(hours=8))

    def send(self, content):
        if not self.webhook:
            print("未配置Webhook")
            return False
        data = {"msgtype": "markdown", "markdown": {"content": content}}
        try:
            r = requests.post(self.webhook, json=data, timeout=15)
            return r.status_code == 200
        except Exception as e:
            print(f"发送失败: {e}")
            return False

    def get_data(self, date):
        try:
            df = ak.stock_notice_report(date=date)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            print(f"{date} 获取数据失败: {e}")
        return None

    # ---------- 改动点 1：重写 filter 方法，实现方案A ----------
    def filter(self, df):
        if df is None or df.empty:
            return pd.DataFrame()
        if '公告标题' not in df.columns:
            print(f"警告: 数据无'公告标题'列, 实际列: {df.columns.tolist()}")
            return pd.DataFrame()

        # 定义三类公告的匹配规则
        patterns = {
            '员工持股计划': r'员工持股计划',
            '股权激励草案': r'限制性股票激励计划.*草案|股票期权激励计划.*草案',
            '回购注销': r'回购.*注销|回购.*通知债权人|减少注册资本.*回购'
        }

        # 综合正则：任意一类命中即入选
        all_pattern = '|'.join(f'({p})' for p in patterns.values())
        mask = df['公告标题'].str.contains(all_pattern, na=False, regex=True)
        filtered = df[mask].copy()

        if filtered.empty:
            return filtered

        # 标注公告类型（按 patterns 顺序优先标注，即员工持股计划优先级最高）
        def label_type(title):
            for name, pat in patterns.items():
                if pd.Series([title]).str.contains(pat, na=False, regex=True).iloc[0]:
                    return name
            return '其他'

        filtered['公告类型'] = filtered['公告标题'].apply(label_type)
        return filtered
    # --------------------------------------------------------

    def run(self):
        now = datetime.now(self.tz)
        today6 = now.replace(hour=6, minute=0, second=0, microsecond=0)
        day1 = (today6 - timedelta(days=1)).strftime("%Y%m%d")
        day2 = today6.strftime("%Y%m%d")

        dfs = []
        for d in [day1, day2]:
            data = self.get_data(d)
            if data is not None:
                dfs.append(data)

        if dfs:
            df_all = pd.concat(dfs, ignore_index=True)
        else:
            df_all = None

        result = self.filter(df_all)

        # ---------- 改动点 2：推送标题和内容适配三类公告 ----------
        title = "📢 员工持股/股权激励/回购注销 监控"
        time_str = f"统计时段: {(today6 - timedelta(days=1)).strftime('%Y-%m-%d')} 06:00 ~ {today6.strftime('%Y-%m-%d')} 06:00"

        if result.empty:
            msg = f"{title}\n\n{time_str}\n\n✅ 本时段无符合条件的公告"
        else:
            # 按类型分组统计，让推送信息更清晰
            type_counts = result['公告类型'].value_counts().to_dict()
            count_str = "、".join([f"{k}:{v}条" for k, v in type_counts.items()])
            msg = f"{title}\n\n{time_str}\n\n共 **{len(result)}** 条 ({count_str})\n\n"

            for i, (_, r) in enumerate(result.iterrows(), 1):
                code = str(r.get("代码", "")).zfill(6)
                name = r.get("名称", "")
                tit = r.get("公告标题", "")[:80]
                url = r.get("公告链接", "")
                ann_type = r.get('公告类型', '')
                # 类型标签用反引号包裹，在 Markdown 中显示为代码块样式
                if pd.notna(url) and url:
                    msg += f"{i}. **{code} {name}** `[{ann_type}]`\n[{tit}]({url})\n\n"
                else:
                    msg += f"{i}. **{code} {name}** `[{ann_type}]`\n{tit}\n\n"
        # --------------------------------------------------------

        self.send(msg)
        print("执行完成")

if __name__ == "__main__":
    StockBot().run()
