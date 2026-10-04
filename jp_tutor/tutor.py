"""Japanese learning agent (CLI). Run: python -m jp_tutor.tutor

LLM (OpenAI-compatible) generates and grades questions when OPENAI_API_KEY is set
(optional OPENAI_BASE_URL, JP_MODEL). Without it, a small built-in bank is used.
Voice (SpeechRecognition mic + TTS) is optional; falls back to typed input.
"""
import difflib
import json
import os
import random
import sqlite3
import time

DB = os.environ.get("JP_HISTORY_DB", os.path.expanduser("~/.jp_tutor.db"))
LEVELS = ["N5", "N4", "N3", "N2", "N1"]

BANK = {  # (prompt, answer, kind)
    "N5": [("Say in Japanese: 'I eat sushi.'", "私は寿司を食べます", "speak"),
           ("Say in Japanese: 'Where is the station?'", "駅はどこですか", "speak"),
           ("Write in Japanese: 'This is a book.'", "これは本です", "write")],
    "N4": [("Say in Japanese: 'I want to go to Japan.'", "日本に行きたいです", "speak"),
           ("Write in Japanese: 'I am reading a book now.'", "今本を読んでいます", "write")],
    "N3": [("Say in Japanese: 'I decided to study every day.'", "毎日勉強することにしました", "speak")],
    "N2": [("Write in Japanese: 'Despite the rain, we went out.'", "雨にもかかわらず出かけた", "write")],
    "N1": [("Write in Japanese: 'It goes without saying that health matters.'",
            "健康が大切なのは言うまでもない", "write")],
}


def db():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY, ts REAL,
        level TEXT, focus TEXT, kind TEXT, prompt TEXT, expected TEXT, answer TEXT,
        correct INTEGER, feedback TEXT)""")
    return c


def llm(system, user):
    from openai import OpenAI
    r = OpenAI().chat.completions.create(
        model=os.environ.get("JP_MODEL", "gpt-4o-mini"),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"})
    return json.loads(r.choices[0].message.content)


def use_llm():
    return bool(os.environ.get("OPENAI_API_KEY"))


def make_question(level, focus, kind, c):
    if use_llm():
        mistakes = [r[0] for r in c.execute(
            "SELECT prompt FROM history WHERE correct=0 AND level=? ORDER BY ts DESC LIMIT 5", (level,))]
        return llm('Return JSON {"prompt": English instruction, "expected": model Japanese answer}. '
                   "Design one JLPT practice question.",
                   f"Level {level}, focus: {focus}, type: {kind}. Past mistakes to reinforce: {mistakes}")
    pool = [q for q in BANK[level] if q[2] == kind] or BANK[level]
    p, a, _ = random.choice(pool)
    return {"prompt": p, "expected": a}


def grade(level, q, answer):
    if use_llm():
        r = llm('Return JSON {"correct": bool, "corrected": Japanese, "explanation": English}. '
                "Be tolerant of kana/kanji variants and minor speech-recognition errors.",
                f"Level {level}. Question: {q['prompt']}. Model answer: {q['expected']}. Student: {answer}")
        return bool(r["correct"]), r["corrected"], r["explanation"]
    norm = lambda s: "".join(ch for ch in s if ch not in "。、 　.,!?！？")
    ratio = difflib.SequenceMatcher(None, norm(answer), norm(q["expected"])).ratio()
    ok = ratio >= 0.95
    return ok, q["expected"], f"Similarity {ratio:.0%} to the model answer."


# ---- voice helpers (optional) ----
def speak(text):
    print("🔊", text)
    try:
        import pyttsx3
        e = pyttsx3.init()
        e.setProperty("voice", next((v.id for v in e.getProperty("voices")
                                     if "ja" in (str(v.languages) + v.id).lower()), e.getProperty("voice")))
        e.say(text)
        e.runAndWait()
    except Exception:
        try:
            from gtts import gTTS
            from playsound import playsound
            gTTS(text, lang="ja").save("/tmp/jp_tts.mp3")
            playsound("/tmp/jp_tts.mp3")
        except Exception:
            pass


def listen():
    try:
        import speech_recognition as sr
        r = sr.Recognizer()
        with sr.Microphone() as src:
            print("🎤 Listening... speak now")
            r.adjust_for_ambient_noise(src, 0.5)
            audio = r.listen(src, timeout=10, phrase_time_limit=15)
        text = r.recognize_google(audio, language="ja-JP")
        print("You said:", text)
        return text
    except Exception as e:
        print(f"(Mic unavailable: {e}) Type your answer instead.")
        return input("> ").strip()


def show_mistakes(c):
    rows = c.execute("SELECT level,prompt,answer,expected,COUNT(*) n FROM history WHERE correct=0 "
                     "GROUP BY prompt,expected ORDER BY MAX(ts) DESC LIMIT 20").fetchall()
    for lv, p, a, e, n in rows or []:
        print(f"[{lv}] {p}\n   last said: {a}\n   correct:   {e}   (missed {n}x)")
    if not rows:
        print("No mistakes recorded yet.")


def session():
    c = db()
    level = ""
    while level not in LEVELS:
        level = input("JLPT level (N5/N4/N3/N2/N1): ").strip().upper()
    focus = input("Focus for this session (e.g. particles, て-form, travel, keigo): ").strip() or "general"
    print("Commands at prompt: 'q' quit, 'h' show mistake history. Answer by voice (Enter) or typing.")
    n = 0
    while True:
        kind = "speak" if n % 2 == 0 else "write"
        q = make_question(level, focus, kind, c)
        n += 1
        print(f"\nQ{n} ({'verbal' if kind == 'speak' else 'written'}): {q['prompt']}")
        if kind == "speak":
            cmd = input("Press Enter to speak (or type answer / q / h): ").strip()
            ans = listen() if cmd == "" else cmd
        else:
            ans = input("> ").strip()
        if ans.lower() == "q":
            break
        if ans.lower() == "h":
            show_mistakes(c)
            continue
        ok, corrected, expl = grade(level, q, ans)
        print("✅ Correct!" if ok else f"❌ Not quite.\n   Suggested: {corrected}")
        print("  ", expl)
        if not ok:
            speak(corrected)
        c.execute("INSERT INTO history(ts,level,focus,kind,prompt,expected,answer,correct,feedback) "
                  "VALUES(?,?,?,?,?,?,?,?,?)",
                  (time.time(), level, focus, kind, q["prompt"], corrected if not ok else q["expected"],
                   ans, int(ok), expl))
        c.commit()
    show_mistakes(c)


if __name__ == "__main__":
    session()
