#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions 云端每日 21:30:00 (北京时间 UTC+8) 精准 Bark 推送脚本
核心机制：
1. 错峰启动：由 GitHub Actions 在 21:12 (UTC 13:12，避开整点/半点全球排队高峰) 提前唤醒容器。
2. 秒级卡点：若容器在 21:00 ~ 21:30 之间提前启动，脚本自动等待 (sleep) 到北京时间 21:30:00 整准时发出推送！
3. 夜间熔断：若 GitHub 队列发生极端延迟（超过晚上 22:00 才启动），脚本直接拦截退出，绝不在半夜/凌晨打扰用户！
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

    # 仅针对 schedule 定时触发执行“卡点等待”与“夜间防打扰熔断”
    # (手动点击 Run workflow 测试时立即发送，不等待)
    if event_name == "schedule":
        target_today = now_bj.replace(hour=21, minute=30, second=0, microsecond=0)
        cutoff_today = now_bj.replace(hour=22, minute=0, second=0, microsecond=0)
        earliest_today = now_bj.replace(hour=20, minute=50, second=0, microsecond=0)

        # 1. 夜间防打扰熔断：如果不在 20:50 ~ 22:00 之间（例如延迟到了半夜 22:01 以后或凌晨），直接放弃推送
        if now_bj < earliest_today or now_bj > cutoff_today:
            print(f"[夜间防打扰熔断] 当前时间 {time_str} 已超出允许推送窗口 (20:50~22:00)，已自动拦截本次推送，绝不半夜打扰！")
            sys.exit(0)

        # 2. 秒级卡点等待：如果容器在 21:30 之前提前就绪，精准等待到 21:30:00 再发送
        wait_seconds = (target_today - now_bj).total_seconds()
        if wait_seconds > 0:
            print(f"[精准卡点] 容器已提前就绪，正在等待 {int(wait_seconds)} 秒，将于北京时间 21:30:00 准时发送推送...")
            time.sleep(wait_seconds)
            now_bj = get_beijing_now()
            date_str = now_bj.strftime("%Y-%m-%d")
            time_str = now_bj.strftime("%H:%M:%S")

    day_key = str((now_bj.weekday() + 1) % 7)

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "checkin_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

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
    body = config["checklist_template"].replace("{plan}", day_info["plan"])
    if checkin_url:
        body += "\n👉 点击本条通知直接打开手机打卡页面！"

    payload = {
        "title": title,
        "body": body,
        "group": config.get("group", "85to70减脂打卡"),
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
