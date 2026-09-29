import datetime
import os
import logging
import akshare as ak
import pandas as pd
from icalendar import Calendar, Event
import pytz

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def get_upcoming_ipo_stocks():
    """
    通过 AkShare 获取今天及未来的新股申购信息
    """
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    logging.info(f"正在查询自 {today_str} 起的未来新股申购信息...")

    try:
        # 获取 A 股新股申购及中签等详情数据（来源于东方财富）
        ipo_df = ak.stock_ipo_info_em()

        if ipo_df.empty:
            logging.info("未获取到新股数据。")
            return []

        # 格式化申购日期
        ipo_df['申购日期_str'] = ipo_df['申购日期'].astype(str).str.slice(0, 10)

        # 筛选今天及未来申购的新股
        future_ipos = ipo_df[ipo_df['申购日期_str'] >= today_str]

        ipo_list = []
        for _, row in future_ipos.iterrows():
            ipo_date_str = str(row.get('申购日期_str', ''))
            stock_name = str(row.get('股票简称', 'N/A'))
            stock_code = str(row.get('申购代码', 'N/A'))

            if ipo_date_str and ipo_date_str != 'nan':
                ipo_list.append({
                    "name": stock_name,
                    "code": stock_code,
                    "date": ipo_date_str
                })

        logging.info(f"成功查找到 {len(ipo_list)} 条未来申购记录。")
        return ipo_list

    except Exception as e:
        logging.error(f"获取新股数据失败: {e}")
        return []

def generate_ics_file(ipo_list, output_path="ipo.ics"):
    """
    生成 iCalendar (.ics) 订阅文件
    事件时间设置为申购当天的 09:30 - 15:00 (中国标准时间 CST)
    """
    cal = Calendar()
    cal.add('prodid', '-//A-Share IPO Calendar//makiotoha//CN')
    cal.add('version', '2.0')
    cal.add('X-WR-CALNAME', 'A股新股申购日历')
    cal.add('X-WR-TIMEZONE', 'Asia/Shanghai')

    tz = pytz.timezone('Asia/Shanghai')

    for item in ipo_list:
        try:
            # 解析日期
            date_parts = [int(p) for p in item['date'].split('-')]
            year, month, day = date_parts[0], date_parts[1], date_parts[2]

            # 设定当天 09:30 到 15:00
            start_dt = tz.localize(datetime.datetime(year, month, day, 9, 30, 0))
            end_dt = tz.localize(datetime.datetime(year, month, day, 15, 0, 0))

            event = Event()
            event.add('summary', f"今日申购：{item['name']}")
            event.add('dtstart', start_dt)
            event.add('dtend', end_dt)
            event.add('description', f"股票简称: {item['name']}\n申购代码: {item['code']}\n申购时间: 09:30 - 15:00")
            # 唯一标识符 UID，格式为 code-date@ipo
            event.add('uid', f"{item['code']}-{item['date']}@ipo-calendar")

            cal.add_component(event)
        except Exception as e:
            logging.error(f"构建事件失败 ({item}): {e}")

    # 保存文件
    with open(output_path, 'wb') as f:
        f.write(cal.to_ical())
    
    logging.info(f"成功生成 ICS 文件: {os.path.abspath(output_path)}")

def main():
    ipo_list = get_upcoming_ipo_stocks()
    generate_ics_file(ipo_list, output_path="ipo.ics")

if __name__ == "__main__":
    main()
