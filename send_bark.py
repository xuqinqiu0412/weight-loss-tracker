#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions 云端每日 21:30:00 (北京时间 UTC+8) 精准 Bark 推送脚本
支持读取云端 checkin_data.json，在锁屏通知中实时展示今日「学习 + 减脂 + 饮水」打卡进度！
"""

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta

def get_beijing_now():
    tz_beijing = timezone(timedelta(hours=8))
    return datetime.now(tz_beijing)

def main():
    now_bj = get_beijing_now()
    date_str = now_bj.strftime("%Y-%m-%d")
    time_str = now_bj.strftime("%H:%M:%S")
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")

    print(f"[启动检查] 当前北京时间: {date_str} {time_str}, 触发方式: {event_name}")

    if event_name == "schedule":
        target_today = now_bj.replace(hour=21, minute=30, second=0, microsecond=0)
        cutoff_today = now_bj.replace(hour=22, minute=0, second=0, microsecond=0)
        earliest_today = now_bj.replace(hour=20, minute=50, second=0, microsecond=0)

        if now_bj < earliest_today or now_bj > cutoff_today:
            print(f"[夜间防打扰熔断] 当前时间 {time_str} 已超出允许推送窗口 (20:50~22:00)，已自动拦截本次推送，绝不半夜打扰！")
            sys.exit(0)

        wait_seconds = (target_today - now_bj).total_seconds()
        if wait_seconds > 0:
            print(f"[精准卡点] 容器已提前就绪，正在等待 {int(wait_seconds)} 秒，将于北京时间 21:30:00 准时发送推送...")
            time.sleep(wait_seconds)
            now_bj = get_beijing_now()
            date_str = now_bj.strftime("%Y-%m-%d")
            time_str = now_bj.strftime("%H:%M:%S")

    day_key = str((now_bj.weekday() + 1) % 7)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "checkin_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # 读取云端实时打卡数据 checkin_data.json (优先从 data 分支拉取最新打卡状态)
    progress_line = ""
    c_data = None
    try:
        raw_url = f"https://raw.githubusercontent.com/xuqinqiu0412/weight-loss-tracker/data/checkin_data.json?t={int(time.time())}"
        with urllib.request.urlopen(raw_url, timeout=10) as df_resp:
            c_data = json.loads(df_resp.read().decode("utf-8"))
    except Exception:
        data_path = os.path.join(base_dir, "checkin_data.json")
        if os.path.exists(data_path):
            try:
                with open(data_path, "r", encoding="utf-8") as df:
                    c_data = json.load(df)
            except Exception:
                pass

    if c_data:
        try:
            today_rec = (c_data.get("daily") or {}).get(date_str) or {}
            cups_count = len(today_rec.get("cups") or [])
            tasks_map = today_rec.get("tasks") or {}
            done_study = sum(1 for k, v in tasks_map.items() if k.startswith("s") and v)
            done_fit = sum(1 for k, v in tasks_map.items() if k.startswith("t") and v)
            progress_line = f"📊 今日已打卡：📚学业 {done_study}/7 ｜ 🔥塑形 {done_fit}/12 ｜ 💧饮水 {cups_count}/8杯\n"
        except Exception:
            pass

    bark_key = os.environ.get("BARK_KEY") or config.get("bark_key")
    if not bark_key:
        raise ValueError("未找到 BARK_KEY，请检查 checkin_config.json 或环境变量")

    checkin_url = os.environ.get("CHECKIN_URL", "").strip()
    gh_repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not checkin_url and "/" in gh_repo:
        owner, repo = gh_repo.split("/", 1)
        if repo.lower() == f"{owner.lower()}.github.io":
            checkin_url = f"https://{owner}.github.io/"
        else:
            checkin_url = f"https://{owner}.github.io/{repo}/"

    day_info = config["days"][day_key]
    title = f"{config['title_prefix']} ({date_str} {day_info['name']})"
    body = progress_line + config["checklist_template"].replace("{study}", day_info.get("study", "")).replace("{plan}", day_info["plan"])
    if checkin_url:
        body += "\n👉 点击本条通知直接打开云同步打卡页！"

    payload = {
        "title": title,
        "body": body,
        "group": config.get("group", "减脂与CPA打卡"),
        "sound": config.get("sound", "bell"),
        "isArchive": "1"
    }
    if checkin_url:
        payload["url"] = checkin_url

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=f"https://api.day.app/{bark_key}",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        resp_body = resp.read().decode("utf-8")
        print(f"[推送成功] 北京时间 {date_str} {time_str}: {resp_body}")
        if checkin_url:
            print(f"[跳转链接] {checkin_url}")

if __name__ == "__main__":
    main()
