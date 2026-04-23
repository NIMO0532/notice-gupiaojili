# -*- coding: utf-8 -*-
"""
A股回购/员工持股计划公告推送
部署：GitHub Actions
自动时间：每天北京时间 06:00
安全说明：Webhook 从环境变量读取，不上传到 GitHub
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta, timezone
import requests
import os

class StockBot:
    def __init__(self):
        # 从环境变量读取 Webhook，代码里不暴露
        self.webhook = os.getenv("WECHAT_WEBHOOK_URL")
        self.tz = timezone(timedelta(hours=8))

    def send(self, content):
        if not self.webhook:
            print("❌ 未配置 Webhook")
            return False
        
        data = {
            "msgtype": "markdown",
            "markdown": {"content": content}
        }
        try:
            requests.post(self.webhook, json=data, timeout=10)
            return True
        except Exception as e:
            print(f"发送失败：{e}")
            return False

    def get_data(self, date):
        try:
            df = ak.stock_notice_report(date=date)
            return df if not df.empty else None
        except:
            return None

    def filter(self, df):
        if df is None or '公告标题' not in df.columns:
            return pd.DataFrame()

        types = ['员工持股计划', '回购公司股份', '股票回购']
        must = ['资金总额', '专户']

        mask1 = df['公告标题'].str.contains('|'.join(types), na=False)
        mask2 = df['公告标题'].str.contains('|'.join(must), na=False)
        return df[mask1 & mask2].copy()

    def run(self):
        now = datetime.now(self.tz)
        today6 = now.replace(hour=6, minute=0, second=0)
        day1 = (today6 - timedelta(days=1)).strftime("%Y%m%d")
        day2 = today6.strftime("%Y%m%d")

        dfs = []
        for d in [day1, day2]:
            data = self.get_data(d)
            if data is not None:
                dfs.append(data)

        result = self.filter(pd.concat(dfs, ignore_index=True) if dfs else None)

        title = "📢 A股回购/员工持股计划公告推送"
        time_info = f"统计时间：{(today6 - timedelta(days=1)).strftime('%Y-%m-%d')} 06:00 ~ {today6.strftime('%Y-%m-%d')} 06:00"

        if len(result) == 0:
            msg = f"{title}\n\n{time_info}\n\n✅ 今日无符合条件公告"
        else:
            msg = f"{title}\n\n{time_info}\n\n共 {len(result)} 条\n\n"
            for i, (_, r) in enumerate(result.iterrows(), 1):
                code = str(r.get('代码', ''))[-6:].zfill(6)
                name = r.get('名称', '')
                title = r.get('公告标题', '')[:60]
                url = r.get('公告链接', '')
                if pd.notna(url):
                    msg += f"{i}. **[{code} {name}]** [{title}]({url})\n"
                else:
                    msg += f"{i}. **[{code} {name}]** {title}\n"

        self.send(msg)
        print("✅ 推送完成")

if __name__ == "__main__":
    StockBot().run()