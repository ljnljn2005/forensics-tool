from src.ai_interface import AiInterface


def run_ai_analysis(text: str) -> dict:
    result = AiInterface.analyze_with_ai(None, text)
    return {
        "text": text,
        "result": result,
    }
