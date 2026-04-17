"""
MiniMax Quota 显示子系统
每次对话/任务完成后显示额度情况
"""
import json
import subprocess
import sys


def get_minimax_quota():
    """通过 mmx-cli 获取 MiniMax 额度"""
    try:
        result = subprocess.run(
            ["/home/xiemeiling/.hermes/node/bin/mmx", "quota", "show"],
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode != 0:
            return None, f"mmx quota failed: {result.stderr}"
        
        data = json.loads(result.stdout)
        models = data.get("model_remains", [])
        return models, None
    except subprocess.TimeoutExpired:
        return None, "mmx quota timeout"
    except json.JSONDecodeError:
        return None, f"mmx quota parse error: {result.stdout[:100]}"
    except FileNotFoundError:
        return None, "mmx-cli not found"
    except Exception as e:
        return None, str(e)


def format_quota_report(models):
    """格式化额度报告"""
    lines = ["**📊 MiniMax 额度情况**\n"]
    
    for m in models:
        name = m.get("model_name", "unknown")
        # MiniMax字段语义：usage_count = 剩余额度，total_count = 总额度
        remain = m.get("current_interval_usage_count", 0)
        total = m.get("current_interval_total_count", 0)
        
        # 换算时间
        remain_ms = m.get("remains_time", 0)
        hours = remain_ms // 3600000
        mins = (remain_ms % 3600000) // 60000
        
        # 图标
        if total == 0:
            pct = 0
            bar = "░░░░░░░░░░"
        else:
            pct = remain / total * 100   # 剩余比例（越大越充足）
            filled = int(pct / 10)
            bar = "█" * filled + "░" * (10 - filled)
        
        # 分类显示
        if "MiniMax-M" in name or name == "MiniMax":
            icon = "🤖"
            type_name = "文本模型"
        elif "speech" in name:
            icon = "🎙"
            type_name = "语音"
        elif "Hailuo" in name:
            icon = "🎬"
            type_name = "视频"
        elif "music" in name:
            icon = "🎵"
            type_name = "音乐"
        elif "image" in name:
            icon = "🖼"
            type_name = "图像"
        elif "coding-plan" in name:
            icon = "🔍"
            type_name = "搜索"
        elif "lyrics" in name:
            icon = "📝"
            type_name = "歌词"
        else:
            icon = "📦"
            type_name = name
        
        # 时间周期
        start = m.get("start_time", 0)
        end = m.get("end_time", 0)
        
        lines.append(f"{icon} **{name}** ({type_name})")
        lines.append(f"   {bar} {remain}/{total} 本周期剩余")
        if hours > 0:
            lines.append(f"   ⏱️  周期剩余: ~{hours}h{mins}m")
        lines.append("")
    
    return "\n".join(lines)


def main():
    """CLI入口"""
    models, err = get_minimax_quota()
    if err:
        print(f"获取额度失败: {err}", file=sys.stderr)
        sys.exit(1)
    
    print(format_quota_report(models))


if __name__ == "__main__":
    main()
