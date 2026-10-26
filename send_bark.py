#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions 云端每日 21:30 (北京时间 UTC+8) Bark 推送脚本
推送通知自带 GitHub Pages 打卡网页跳转链接，在 iPhone 上点击通知即可直接进入打卡页面！
"""

import json
import os
import urllib.request
from datetime import datetime, timezone, timedelta

def main():
    # 计算北京时间 (UTC+8)
    tz_beijing = timezone(timedelta(hours=8))
    now_bj = datetime.now(tz_beijing)
    date_str = now_bj.strftime("%Y-%m-%d")
    # Python weekday(): Monday=0 ... Sunday=6 -> 转换为 Sunday=0, Monday=1 ... Saturday=6
    day_key = str((now_bj.weekday() + 1) % 7)

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "checkin_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # 优先使用环境变量中的 BARK_KEY（如果配置了 GitHub Secrets），否则回退到 checkin_config.json
    bark_key = os.environ.get("BARK_KEY") or config.get("bark_key")
    if not bark_key:
        raise ValueError("未找到 BARK_KEY，请检查 checkin_config.json 或环境变量")

    # 自动根据 GITHUB_REPOSITORY 生成 GitHub Pages 手机端打卡网址
    # 例如仓库为 username/weight-loss-tracker -> https://username.github.io/weight-loss-tracker/
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
        print(f"Bark Push Success ({date_str}): {resp_body}")
        if checkin_url:
            print(f"Attached Check-in URL: {checkin_url}")

if __name__ == "__main__":
    main()
