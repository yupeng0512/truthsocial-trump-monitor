"""消息格式化工具

提供统一的格式化函数，避免重复代码。
"""

from typing import Optional


# ==================== 常量映射 ====================

SENTIMENT_MAP = {
    "bullish": "看涨📈",
    "bearish": "看跌📉", 
    "neutral": "中性➡️",
    "mixed": "混合↔️",
}

IMPACT_MAP = {
    "high": "高🔴",
    "medium": "中🟡",
    "low": "低🟢",
    "none": "无",
}

DIRECTION_MAP = {
    "long": "做多📈",
    "short": "做空📉",
    "hedge": "对冲🛡️",
    "hedge/short": "对冲/做空🛡️",
}


# ==================== 格式化函数 ====================


def format_ai_analysis(
    ai_analysis: Optional[dict],
    style: str = "full",
    title: str = "🤖 AI 分析",
) -> str:
    """统一的 AI 分析格式化函数
    
    Args:
        ai_analysis: AI 分析结果字典
        style: 格式化风格
            - "full": 完整显示（默认）
            - "compact": 紧凑显示（用于批量推送中的单条）
            - "summary": 仅显示摘要
        title: 标题文本
        
    Returns:
        格式化后的字符串
    """
    if not ai_analysis:
        return ""
    
    lines = [title]
    
    # 核心结论
    summary = ai_analysis.get("summary", {})
    if summary:
        if headline := summary.get("headline"):
            lines.append(f"   📌 {headline}")
        
        sentiment = summary.get("overall_sentiment", "")
        impact = summary.get("market_impact_level", "")
        urgency = summary.get("urgency", "")
        
        meta_parts = []
        if sentiment:
            meta_parts.append(f"情绪:{SENTIMENT_MAP.get(sentiment, sentiment)}")
        if impact:
            meta_parts.append(f"影响:{IMPACT_MAP.get(impact, impact)}")
        if urgency:
            meta_parts.append(f"紧迫性:{urgency}")
        
        if meta_parts:
            lines.append(f"   {' | '.join(meta_parts)}")
    
    if style == "summary":
        return "\n".join(lines)
    
    # 投资建议
    recommendations = ai_analysis.get("investment_recommendations", [])
    if recommendations:
        lines.append("")
        lines.append("   💡 投资建议:")
        for rec in recommendations:
            category = rec.get("category", "")
            direction = rec.get("direction", "")
            confidence = rec.get("confidence", 0)
            ticker = rec.get("ticker", "")
            
            dir_text = DIRECTION_MAP.get(direction, direction)
            line = f"  • {category} ({dir_text}, 置信度:{confidence}%)"
            if ticker:
                line += f"\n  标的: {ticker}"
            lines.append(line)
    
    # 风险提示
    warnings = ai_analysis.get("risk_warnings", [])
    if warnings:
        lines.append("")
        lines.append("   ⚠️ 风险提示:")
        for w in warnings:
            lines.append(f"  • {w}")
    
    # 后续关注（仅完整模式）
    if style == "full":
        follow_up = ai_analysis.get("follow_up_signals", [])
        if follow_up:
            lines.append("")
            lines.append("   👀 后续关注:")
            for f in follow_up:
                lines.append(f"  • {f}")
    
    return "\n".join(lines)


def format_ai_analysis_markdown(
    ai_analysis: Optional[dict],
    title: str = "🤖 AI 分析",
) -> str:
    """AI 分析 Markdown 格式化
    
    Args:
        ai_analysis: AI 分析结果字典
        title: 标题文本
        
    Returns:
        Markdown 格式的字符串
    """
    if not ai_analysis:
        return ""
    
    lines = [f"**{title}**\n"]
    
    # 核心结论
    summary = ai_analysis.get("summary", {})
    if summary:
        if headline := summary.get("headline"):
            lines.append(f"📌 **{headline}**\n")
        
        sentiment = summary.get("overall_sentiment", "")
        impact = summary.get("market_impact_level", "")
        
        if sentiment or impact:
            parts = []
            if sentiment:
                parts.append(f"情绪: {SENTIMENT_MAP.get(sentiment, sentiment)}")
            if impact:
                parts.append(f"影响: {IMPACT_MAP.get(impact, impact)}")
            lines.append(f"{' | '.join(parts)}\n")
    
    # 投资建议
    recommendations = ai_analysis.get("investment_recommendations", [])
    if recommendations:
        lines.append("**💡 投资建议**\n")
        for rec in recommendations:
            category = rec.get("category", "")
            direction = rec.get("direction", "")
            confidence = rec.get("confidence", 0)
            ticker = rec.get("ticker", "")
            time_horizon = rec.get("time_horizon", "")
            
            dir_emoji = {"long": "📈", "short": "📉", "hedge": "🛡️"}.get(direction, "")
            lines.append(f"{dir_emoji} **{category}** (置信度: {confidence}%)")
            
            if ticker:
                lines.append(f"  • 标的: {ticker}")
            if time_horizon:
                lines.append(f"  • 时间窗口: {time_horizon}")
            lines.append("")
    
    # 风险提示
    warnings = ai_analysis.get("risk_warnings", [])
    if warnings:
        lines.append("**⚠️ 风险提示**")
        for w in warnings:
            lines.append(f"• {w}")
        lines.append("")
    
    # 后续关注
    follow_up = ai_analysis.get("follow_up_signals", [])
    if follow_up:
        lines.append("**👀 后续关注**")
        for f in follow_up:
            lines.append(f"• {f}")
    
    return "\n".join(lines)
