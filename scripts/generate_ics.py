import datetime
import os
import logging
import akshare as ak
import pandas as pd
from icalendar import Calendar, Event
import pytz

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def get_upcoming_ipo_stocks():
    """
    通过 AkShare 获取包含当天及未来的全板块新股申购信息
    """
    # 获取运行当天的动态日期（格式: YYYY-MM-DD）
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    logging.info(f"正在查询自 {today_str} 起的未来新股申购信息...")

    try:
        # 使用最新 AKShare 接口获取新股申购日历数据（覆盖沪、深、京交所全板块）
        ipo_df = ak.stock_ipo_ths()

        if ipo_df is None or ipo_df.empty:
            logging.info("未获取到新股数据或返回为空。")
            return []

        # 检查关键列名（如果接口字段变更，进行兼容处理）
        date_col = None
        for col in ['申购日期', '上网申购日', '申购日']:
            if col in ipo_df.columns:
                date_col = col
                break

        if not date_col:
            logging.error(f"未在返回数据中找到申购日期字段，当前列名: {list(ipo_df.columns)}")
            return []

        name_col = '股票简称' if '股票简称' in ipo_df.columns else '证券简称'
        code_col = '申购代码' if '申购代码' in ipo_df.columns else '证券代码'

        # 转换并清洗申购日期列
        ipo_df['申购日期_str'] = pd.to_datetime(ipo_df[date_col], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # 过滤掉日期解析失败的行
        valid_df = ipo_df.dropna(subset=['申购日期_str'])

        # 筛选“申购日期 >= 今天”的新股数据
        future_ipos = valid_df[valid_df['申购日期_str'] >= today_str]

        ipo_list = []
        for _, row in future_ipos.iterrows():
            ipo_date_str = str(row.get('申购日期_str', ''))
            stock_name = str(row.get(name_col, 'N/A')).strip()
            stock_code = str(row.get(code_col, 'N/A')).strip()

            if ipo_date_str and ipo_date_str != 'NaT':
                ipo_list.append({
                    "name": stock_name,
                    "code": stock_code,
                    "date": ipo_date_str
                })

        # 去重处理（避免接口重复返回同一只股票）
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
        logging.error(f"获取新股数据发生异常: {e}")
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
    
    logging.info(f"已成功写入文件: {os.path.abspath(output_path)}")

def main():
    ipo_list = get_upcoming_ipo_stocks()
    generate_ics_file(ipo_list, output_path="ipo.ics")

if __name__ == "__main__":
    main()
