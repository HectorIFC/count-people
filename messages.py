"""User-facing bot messages in Portuguese, English and Spanish.

The reply language is picked per message from the sender's Telegram client
language (Update.effective_user.language_code). Unsupported languages fall
back to English.
"""

from analysis import AGE_GROUPS, CountResult

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ("pt", "en", "es")

MESSAGES = {
    "start": {
        "pt": (
            "Olá! Me envie uma foto ou um vídeo do local e eu conto as pessoas.\n\n"
            "Foto: contagem em segundos.\n"
            "Vídeo: panorâmica lenta de 20-30s; conto pessoas únicas com tracking "
            "(pode demorar vários minutos).\n\n"
            "Dica: escreva o nome do evento na legenda "
            '(ex: "Reunião de domingo") para organizar o histórico.\n\n'
            "Os arquivos são apagados após a análise; apenas os números "
            "agregados são mantidos."
        ),
        "en": (
            "Hi! Send me a photo or a video of the venue and I will count the people.\n\n"
            "Photo: counted within seconds.\n"
            "Video: slow 20-30s pan; I count unique people with tracking "
            "(it can take several minutes).\n\n"
            "Tip: write the event name in the caption "
            '(e.g. "Sunday meeting") to organize the history.\n\n'
            "Files are deleted right after the analysis; only aggregated "
            "numbers are kept."
        ),
        "es": (
            "¡Hola! Envíame una foto o un video del lugar y cuento las personas.\n\n"
            "Foto: conteo en segundos.\n"
            "Video: panorámica lenta de 20-30s; cuento personas únicas con tracking "
            "(puede tardar varios minutos).\n\n"
            "Consejo: escribe el nombre del evento en el pie de foto "
            '(ej. "Reunión de domingo") para organizar el historial.\n\n'
            "Los archivos se borran tras el análisis; solo se conservan los "
            "números agregados."
        ),
    },
    "photo_received": {
        "pt": "Foto recebida, analisando...",
        "en": "Photo received, analyzing...",
        "es": "Foto recibida, analizando...",
    },
    "photo_failed": {
        "pt": "Não consegui analisar esta foto. Tente outra imagem.",
        "en": "I could not analyze this photo. Please try another image.",
        "es": "No pude analizar esta foto. Prueba con otra imagen.",
    },
    "video_too_large": {
        "pt": (
            "Este vídeo passa de 20 MB, o limite que o Telegram permite a bots "
            "baixarem. Grave um trecho mais curto (20-30s em 720p) e envie de novo."
        ),
        "en": (
            "This video exceeds 20 MB, the limit Telegram allows bots to "
            "download. Record a shorter clip (20-30s at 720p) and send it again."
        ),
        "es": (
            "Este video supera los 20 MB, el límite que Telegram permite "
            "descargar a los bots. Graba un clip más corto (20-30s en 720p) y "
            "envíalo de nuevo."
        ),
    },
    "video_received": {
        "pt": (
            "Vídeo recebido: {duration:.0f}s, {frames} frames. Processando com "
            "tracking, isso pode levar vários minutos..."
        ),
        "en": (
            "Video received: {duration:.0f}s, {frames} frames. Processing with "
            "tracking, this can take several minutes..."
        ),
        "es": (
            "Video recibido: {duration:.0f}s, {frames} frames. Procesando con "
            "tracking, esto puede tardar varios minutos..."
        ),
    },
    "video_failed": {
        "pt": "Não consegui analisar este vídeo. Tente um arquivo .mp4 mais curto.",
        "en": "I could not analyze this video. Please try a shorter .mp4 file.",
        "es": "No pude analizar este video. Prueba con un archivo .mp4 más corto.",
    },
    "annotated_caption": {
        "pt": "Prévia anotada (idades estimadas)",
        "en": "Annotated preview (estimated ages)",
        "es": "Vista previa anotada (edades estimadas)",
    },
    "summary_title": {
        "pt": "Resumo - {label}",
        "en": "Summary - {label}",
        "es": "Resumen - {label}",
    },
    "summary_total": {
        "pt": "Total de pessoas: {count}",
        "en": "Total people: {count}",
        "es": "Total de personas: {count}",
    },
    "summary_analyzed": {
        "pt": "Com demografia estimada: {count}",
        "en": "With estimated demographics: {count}",
        "es": "Con demografía estimada: {count}",
    },
    "default_event_label": {
        "pt": "Evento",
        "en": "Event",
        "es": "Evento",
    },
}

AGE_GROUP_LABELS = {
    "child": {"pt": "Crianças", "en": "Children", "es": "Niños"},
    "teen": {"pt": "Adolescentes", "en": "Teens", "es": "Adolescentes"},
    "adult": {"pt": "Adultos", "en": "Adults", "es": "Adultos"},
    "senior": {"pt": "Idosos", "en": "Seniors", "es": "Mayores"},
}


def resolve_language(language_code: str | None) -> str:
    """Telegram sends IETF tags like "pt-br"; keep only the primary subtag."""
    if not language_code:
        return DEFAULT_LANGUAGE
    primary = language_code.split("-")[0].lower()
    return primary if primary in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def message(key: str, lang: str, **kwargs) -> str:
    return MESSAGES[key][lang].format(**kwargs)


def format_summary(result: CountResult, event_label: str, lang: str) -> str:
    lines = [
        message("summary_title", lang, label=event_label),
        message("summary_total", lang, count=result.total_people),
        message("summary_analyzed", lang, count=result.analyzed_individuals),
        "",
    ]
    for age_group in AGE_GROUPS:
        male = result.demographics.get(f"{age_group}_M", 0)
        female = result.demographics.get(f"{age_group}_F", 0)
        if male or female:
            lines.append(f"{AGE_GROUP_LABELS[age_group][lang]}: {male} M, {female} F")
    return "\n".join(lines)
