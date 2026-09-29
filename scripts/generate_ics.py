import datetime
import os
import logging
import re
import akshare as ak
import pandas as pd
from icalendar import Calendar, Event
import pytz

# 配置日志输出格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def clean_date_string(val):
    """
    正则提取字符串中的 YYYY-MM-DD 日期格式，避免非标准字符干扰
    """
    if pd.isna(val) or not val:
        return None
    val_str = str(val).strip()
    match = re.search(r'\d{4}-\d{2}-\d{2}', val_str)
    if match:
        return match.group(0)
    return None

def get_upcoming_ipo_stocks():
    """
    通过 AkShare 的 stock_ipo_ths 接口获取全板块未来新股申购信息
    """
    # 获取运行当天的动态日期 (格式: YYYY-MM-DD)
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    logging.info(f"正在查询自 {today_str} 起的未来新股申购信息...")

    try:
        # 调用同花顺新股申购与中签接口
        ipo_df = ak.stock_ipo_ths(symbol="全部A股")

        if ipo_df is None or ipo_df.empty:
            logging.warning("同花顺接口未返回数据，尝试备用逻辑...")
            return []

        # 校验必要字段
        date_col = '申购日期'
        name_col = '股票简称'
        code_col = '申购代码'

        if date_col not in ipo_df.columns:
            logging.error(f"缺失必要字段 '{date_col}'，当前列: {list(ipo_df.columns)}")
            return []

        # 1. 优先正则提取日期，解决 Parsing 警告
        ipo_df['申购日期_clean'] = ipo_df[date_col].apply(clean_date_string)

        # 2. 安全转换为 datetime（明确 format，防止 UserWarning）
        ipo_df['申购日期_dt'] = pd.to_datetime(
            ipo_df['申购日期_clean'], 
            format='%Y-%m-%d', 
            errors='coerce'
        )
        
        # 3. 重新提取为 YYYY-MM-DD 字符串并过滤无效日期
        ipo_df['申购日期_str'] = ipo_df['申购日期_dt'].dt.strftime('%Y-%m-%d')
        valid_df = ipo_df.dropna(subset=['申购日期_str'])

        # 4. 筛选“申购日期 >= 今天”的新股数据
        future_ipos = valid_df[valid_df['申购日期_str'] >= today_str]

        ipo_list = []
        for _, row in future_ipos.iterrows():
            ipo_date_str = str(row.get('申购日期_str', ''))
            stock_name = str(row.get(name_col, 'N/A')).strip()
            stock_code = str(row.get(code_col, 'N/A')).strip()
            price = str(row.get('发行价格', 'N/A')).strip()
            limit_shares = str(row.get('申购上限（万股）', 'N/A')).strip()

            if ipo_date_str:
                ipo_list.append({
                    "name": stock_name,
                    "code": stock_code,
                    "date": ipo_date_str,
                    "price": price,
                    "limit": limit_shares
                })

        # 去重处理
        unique_ipo_list = []
        seen = set()
        for item in ipo_list:
            key = (item['code'], item['date'])
            if key not in seen:
                seen.add(key)
                unique_ipo_list.append(item)

        logging.info(f"成功获取到 {len(unique_ipo_list)} 条未来新股申购记录。")
        return unique_ipo_list

    except Exception as e:
        logging.error(f"获取新股数据发生异常: {e}")
        return []

def generate_ics_file(ipo_list, output_path="ipo.ics"):
    """
    生成 iCalendar (.ics) 文件
    事件时间固定为申购当天的 09:30 - 15:00 (Asia/Shanghai)
    """
    cal = Calendar()
    cal.add('prodid', '-//A-Share IPO Calendar//makiotoha//CN')
    cal.add('version', '2.0')
    cal.add('X-WR-CALNAME', 'A股新股申购日历')
    cal.add('X-WR-TIMEZONE', 'Asia/Shanghai')

    tz = pytz.timezone('Asia/Shanghai')

    for item in ipo_list:
        try:
            date_parts = [int(p) for p in item['date'].split('-')]
            year, month, day = date_parts[0], date_parts[1], date_parts[2]

            start_dt = tz.localize(datetime.datetime(year, month, day, 9, 30, 0))
            end_dt = tz.localize(datetime.datetime(year, month, day, 15, 0, 0))

            event = Event()
            event.add('summary', f"今日申购：{item['name']}")
            event.add('dtstart', start_dt)
            event.add('dtend', end_dt)
            
            desc = (
                f"股票简称: {item['name']}\n"
                f"申购代码: {item['code']}\n"
                f"发行价格: {item['price']} 元\n"
                f"申购上限: {item['limit']} 万股\n"
                f"申购时间: 09:30 - 15:00"
            )
            event.add('description', desc)
            event.add('uid', f"{item['code']}-{item['date']}@ipo-calendar")

            cal.add_component(event)
        except Exception as e:
            logging.error(f"构建日历事件失败 ({item}): {e}")

    with open(output_path, 'wb') as f:
        f.write(cal.to_ical())
    
    logging.info(f"已生成日历文件: {os.path.abspath(output_path)}")

def main():
    ipo_list = get_upcoming_ipo_stocks()
    generate_ics_file(ipo_list, output_path="ipo.ics")

if __name__ == "__main__":
    main()
