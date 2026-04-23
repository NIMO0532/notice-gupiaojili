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
        
        data = {
            "msgtype": "markdown",
            "markdown": {"content": content}
        }
        try:
            requests.post(self.webhook, json=data, timeout=15)
            return True
        except:
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

        type_words = ["员工持股计划", "回购公司股份", "股票回购"]
        must_words = ["资金总额", "专户"]

        mask1 = df["公告标题"].str.contains('|'.join(type_words), na=False)
        mask2 = df["公告标题"].str.contains('|'.join(must_words), na=False)
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

        title = "📢 A股回购/员工持股计划公告"
        time_str = f"统计：{(today6-timedelta(days=1)).strftime('%Y-%m-%d')} 06:00 ~ {today6.strftime('%Y-%m-%d')} 06:00"

        if len(result) == 0:
            msg = f"{title}\n\n{time_str}\n\n✅ 今日无符合条件公告"
        else:
            msg = f"{title}\n\n{time_str}\n\n共 {len(result)} 条\n\n"
            for i, (_, r) in enumerate(result.iterrows(), 1):
                code = str(r.get("代码", ""))[-6:].zfill(6)
                name = r.get("名称", "")
                title = r.get("公告标题", "")[:60]
                url = r.get("公告链接", "")
                if pd.notna(url):
                    msg += f"{i}. **{code} {name}**\n[{title}]({url})\n\n"
                else:
                    msg += f"{i}. **{code} {name}**\n{title}\n\n"

        self.send(msg)
        print("执行完成")

if __name__ == "__main__":
    StockBot().run()
