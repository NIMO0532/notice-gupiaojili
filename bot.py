# -*- coding: utf-8 -*-
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta, timezone
import requests
import re
import os

class StockBot:
    def __init__(self):
        self.webhook = os.getenv("WECHAT_WEBHOOK_URL")
        self.tz = timezone(timedelta(hours=8))
        
        # 宽松匹配：每股XX元 / XX元/股
        self.price_reg = re.compile(
            r'每股\s*(\d+\.\d+|\d+)\s*元|(\d+\.\d+|\d+)\s*元[/／]股',
            re.IGNORECASE | re.S
        )

    def send(self, content):
        if not self.webhook:
            print("未配置Webhook")
            return False
        content = content[:4000]
        data = {"msgtype": "markdown", "markdown": {"content": content}}
        try:
            r = requests.post(self.webhook, json=data, timeout=15)
            print("推送发送成功")
            return r.status_code == 200
        except Exception as e:
            print(f"发送失败: {e}")
            return False

    # 获取公告数据
    def get_data(self, date):
        try:
            df = ak.stock_news_report(date=date)
            return df if df is not None and not df.empty else None
        except Exception as e:
            print(f"{date} 公告获取失败: {e}")
            return None

    # 提取价格
    def get_notice_price(self, text):
        if not text:
            return None
        res = self.price_reg.findall(text)
        if not res:
            return None
        for item in res:
            for num_str in item:
                if num_str:
                    try:
                        return float(num_str)
                    except:
                        continue
        return None

    # 核心筛选
    def filter(self, df):
        if df is None or df.empty or '标题' not in df.columns:
            return pd.DataFrame()

        # 已扩容最全关键词，无缩进错误
        patterns = {
            '员工持股计划': r'员工持股计划|核心员工持股|管理层持股',
            '股权激励': r'股权激励|限制性股票激励|股票期权激励|限制性股票|期权激励计划|股票激励计划|授予股票|预留限制性股票'
        }
        
        all_pat = '|'.join(patterns.values())
        mask = df['标题'].str.contains(all_pat, na=False, regex=True)
        filtered = df[mask].copy()
        
        if filtered.empty:
            return filtered

        # 类型打标
        def label_type(title):
            for name, pat in patterns.items():
                if re.search(pat, title):
                    return name
            return ""
        
        filtered['公告类型'] = filtered['标题'].apply(label_type)

        # 排序
        sort_map = {"员工持股计划": 0, "股权激励": 1}
        filtered['sort_key'] = filtered['公告类型'].map(sort_map)
        filtered = filtered.sort_values("sort_key").reset_index(drop=True)

        # 提取价格
        price_list = []
        for _, row in filtered.iterrows():
            full_text = f"{row.get('标题','')} {row.get('内容','')}"
            p = self.get_notice_price(full_text)
            price_list.append(p)

        filtered["公告约定价格"] = price_list

        # 价格过滤
        filtered = filtered[
            filtered["公告约定价格"].notna() &
            (filtered["公告约定价格"] >= 5) &
            (filtered["公告约定价格"] <= 20)
        ].copy()

        return filtered

    def run(self):
        now = datetime.now(self.tz)
        day1 = (now - timedelta(days=1)).strftime("%Y%m%d")
        day2 = now.strftime("%Y%m%d")

        dfs = []
        for d in [day1, day2]:
            data = self.get_data(d)
            if data is not None:
                dfs.append(data)

        df_all = pd.concat(dfs, ignore_index=True) if dfs else None
        result = self.filter(df_all)

        title = "📢 员工持股/股权激励监控｜公告价5~20元"
        time_range = f"统计时段：{(now-timedelta(days=1)).strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}"

        if result.empty:
            msg = f"{title}\n\n{time_range}\n\n✅ 本时段无符合条件公告"
        else:
            type_cnt = result['公告类型'].value_counts().to_dict()
            cnt_text = "、".join([f"{k}:{v}条" for k, v in type_cnt.items()])
            msg = f"{title}\n\n{time_range}\n\n合计：**{len(result)}** 条（{cnt_text}）\n\n"

            show_num = min(12, len(result))
            for i, (_, row) in enumerate(result.head(show_num).iterrows(), 1):
                code = str(row["代码"]).zfill(6)
                name = row["名称"]
                price = row["公告约定价格"]
                ann_type = row["公告类型"]
                link = str(row.get("链接", ""))
                short_title = str(row["标题"])[:65]

                if link.startswith("http"):
                    msg += f"{i}. **{code} {name}**｜公告价：{price}元｜`{ann_type}`\n[{short_title}]({link})\n\n"
                else:
                    msg += f"{i}. **{code} {name}**｜公告价：{price}元｜`{ann_type}`\n{short_title}\n\n"

        self.send(msg)
        print("脚本执行完毕")

if __name__ == "__main__":
    try:
        bot = StockBot()
        bot.run()
    except Exception as e:
        print(f"运行异常: {e}")
