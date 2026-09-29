import datetime
import os
import logging
import akshare as ak
import pandas as pd
from icalendar import Calendar, Event
import pytz

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def get_upcoming_ipo_stocks():
    """
    使用同花顺接口 ak.stock_ipo_ths(symbol="全部A股")
    获取当天及未来的全板块新股申购信息
    """
    # 动态获取脚本运行当天的日期（格式: YYYY-MM-DD）
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    logging.info(f"正在通过同花顺接口查询自 {today_str} 起的未来新股申购信息...")

    try:
        # 调用同花顺接口，获取全部A股（含沪深、创业板、科创板、京市主板）的新股申购数据
        ipo_df = ak.stock_ipo_ths(symbol="全部A股")

        if ipo_df is None or ipo_df.empty:
            logging.info("同花顺接口未返回任何新股数据。")
            return []

        # 检查关键字段是否存在
        required_cols = ['申购日期', '股票简称', '申购代码']
        for col in required_cols:
            if col not in ipo_df.columns:
                logging.error(f"同花顺接口返回数据缺少字段: {col}，当前字段: {list(ipo_df.columns)}")
                return []

        # 格式化并清洗申购日期
        ipo_df['申购日期_str'] = pd.to_datetime(ipo_df['申购日期'], errors='coerce').dt.strftime('%Y-%m-%d')
        valid_df = ipo_df.dropna(subset=['申购日期_str'])

        # 筛选“申购日期 >= 今天”的新股
        future_ipos = valid_df[valid_df['申购日期_str'] >= today_str]

        ipo_list = []
        for _, row in future_ipos.iterrows():
            ipo_date_str = str(row.get('申购日期_str', '')).strip()
            stock_name = str(row.get('股票简称', 'N/A')).strip()
            stock_code = str(row.get('申购代码', 'N/A')).strip()

            if ipo_date_str and ipo_date_str != 'NaT':
                ipo_list.append({
                    "name": stock_name,
                    "code": stock_code,
                    "date": ipo_date_str
                })

        # 去重处理（根据 申购代码 + 申购日期）
        unique_ipo_list = []
        seen = set()
        for item in ipo_list:
            key = (item['code'], item['date'])
            if key not in seen:
                seen.add(key)
                unique_ipo_list.append(item)

        logging.info(f"成功获取到 {len(unique_ipo_list)} 条未来申购记录。")
        return unique_ipo_list

    except Exception as e:
        logging.error(f"使用同花顺接口获取新股数据发生异常: {e}")
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

            # 设定申购时间段：09:30 至 15:00
            start_dt = tz.localize(datetime.datetime(year, month, day, 9, 30, 0))
            end_dt = tz.localize(datetime.datetime(year, month, day, 15, 0, 0))

            event = Event()
            event.add('summary', f"今日申购：{item['name']}")
            event.add('dtstart', start_dt)
            event.add('dtend', end_dt)
            event.add('description', f"股票简称: {item['name']}\n申购代码: {item['code']}\n申购时间: 09:30 - 15:00")
            # 唯一标识符 UID，格式: code-date@ipo-calendar
            event.add('uid', f"{item['code']}-{item['date']}@ipo-calendar")

            cal.add_component(event)
        except Exception as e:
            logging.error(f"构建日历事件失败 ({item}): {e}")

    # 保存 .ics 文件
    with open(output_path, 'wb') as f:
        f.write(cal.to_ical())

    logging.info(f"已成功写入订阅文件: {os.path.abspath(output_path)}")

def main():
    ipo_list = get_upcoming_ipo_stocks()
    generate_ics_file(ipo_list, output_path="ipo.ics")

if __name__ == "__main__":
    main()
