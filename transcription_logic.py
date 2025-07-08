import os
import torch
from mutagen.mp3 import MP3
from pydub import AudioSegment
import nltk
from nltk.tokenize import word_tokenize

# NLTK-Ressourcen einmalig herunterladen, falls nicht vorhanden
try:
    nltk.data.find('tokenizers/punkt')
except nltk.downloader.DownloadError:
    nltk.download('punkt')

def count_words_in_german_text(text):
    words = word_tokenize(text, language="german")
    words = [word for word in words if word.isalpha()]
    return len(words)

def get_audio_length_in_minutes(file_path):
    try:
        audio = MP3(file_path)
        return audio.info.length / 60
    except Exception:
        return 0

def process_audio_file(filepath, pipe_instance):
    """
    Verarbeitet eine einzelne Audiodatei, transkribiert sie und generiert Prompts.
    Gibt die Ergebnisse als Dictionary zurück.
    """
    sample = filepath

    # Konvertiere M4A zu MP3 falls nötig
    if sample.endswith(".m4a"):
        audio = AudioSegment.from_file(sample, format="m4a")
        mp3_sample_path = os.path.splitext(sample)[0] + ".mp3"
        audio.export(mp3_sample_path, format="mp3")
        sample = mp3_sample_path

    # Transkription durchführen
    result = pipe_instance(sample)
    result_text = result["text"]

    # Aufräumen: Lösche die konvertierte MP3-Datei, wenn sie erstellt wurde
    if sample != filepath and os.path.exists(sample):
        os.remove(sample)

    # Analyse
    word_count = count_words_in_german_text(result_text)
    audio_length_min = get_audio_length_in_minutes(filepath)
    estimated_reading_time_min = word_count / 220
    summary_word_count = int(word_count * 0.2)

    # Prompts generieren
    prompt_summary = f"Analysiere diesen Text: ``` {result_text} ``` und erstelle mir eine detaillierte Zusammenfassung der Fakten. Extrahiere alle Aufgaben, Themenbereiche und Termine. Erstelle eine Tabelle mit ToDos."
    prompt_presentation = f"Erstelle aus dem folgenden Text einen Vorschlag für eine Präsentation. Gliedere den Inhalt in logische Folien mit Stichpunkten. TEXT: ``` {result_text} ```"
    prompt_journalist = f"Versetze dich in die Rolle einer Journalistin. Fasse mir folgenden Text ``` {result_text} ``` mit mindestens {summary_word_count} Worten in einfacher Sprache und kurzen Sätzen zusammen. Sei neutral und genau."

    # Ergebnis-Dictionary zusammenstellen
    final_output = {
        "audio_duration_minutes": round(audio_length_min, 2),
        "transcription_word_count": word_count,
        "estimated_reading_time_minutes": round(estimated_reading_time_min, 2),
        "transcription": result_text,
        "prompts": {
            "summary_tasks_and_todos": prompt_summary,
            "presentation_structure": prompt_presentation,
            "journalistic_summary": prompt_journalist
        }
    }

    return final_output