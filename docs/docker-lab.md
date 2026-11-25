# שלב 2 — Docker, צעד אחר צעד

## מה השתנה?

אותו קוד Flask נארז ב-Image. קונטיינר מריץ אותו באמצעות Gunicorn, שרת להרצת אפליקציות Python. השרת המקומי הקודם ב-8080 יכול להמשיך לפעול; גרסת Docker נגישה ב-http://127.0.0.1:8081.

```text
דפדפן → localhost:8081 → קונטיינר:8080 → Flask → אתר נבדק
                                           ↓
                                    /app/data/checks.db
                                           ↓
                                    Volume: monitor-data
```

## הקבצים

- `Dockerfile`: הוראות בניית Image ופקודת ההפעלה.
- `.dockerignore`: מונע העתקת מסד מקומי, Git, סביבה וירטואלית וקובצי סודות להקשר הבנייה.
- `compose.yaml`: מגדיר איך להפעיל את הקונטיינר: פורטים, משתני סביבה ו-Volume.

## בנייה והפעלה

מתוך תיקיית הפרויקט:

```bash
docker compose up -d --build --wait
docker compose ps
curl http://127.0.0.1:8081/health
docker compose logs --tail=30 web
```

Compose בונה Image, יוצר Volume אם הוא חסר, יוצר קונטיינר וממתין לבדיקת הבריאות. `-d` משאיר את הקונטיינר ברקע. `EXPOSE` ב-Dockerfile הוא תיעוד; מיפוי `ports` הוא שמאפשר גישה מהמחשב.

## איך הנתונים נשמרים?

SQLite עדיין מנהל קובץ; המיקום בקונטיינר הוא `/app/data/checks.db`. חיברנו Volume לתיקייה `/app/data`. ההיסטוריה המקומית הישנה ב-`data/checks.db` אינה מועתקת ל-Image ולא ל-Volume, ולכן מתחילים כאן היסטוריה נפרדת.

בדיקת התמדה:

1. לחצי Check now ושימי לב לרשומה ולזמן.
2. הריצי `docker compose up -d --force-recreate --wait`.
3. רענני את העמוד: הרשומה צריכה להישאר, למרות שהקונטיינר הוחלף.

זה בודק שהנתונים נשמרים מעבר לחיי הקונטיינר; Volume אינו גיבוי.

## פקודות שימושיות

```bash
docker compose logs --tail=50 web
docker compose exec web sh
docker compose exec web id
docker compose stop
docker compose start
docker compose down
```

`stop` עוצר; `down` מסיר את קונטיינרי ורשת הפרויקט, ומשאיר את ה-Volume כברירת מחדל. אל תוסיפי `--volumes` אם את רוצה לשמור היסטוריה.

## שינוי הגדרה בלי לבנות Image

```bash
MONITOR_PORT=8082 docker compose up -d --wait
```

אותו Image, פורט חיצוני אחר. להחזרה: `docker compose up -d --wait` בלי המשתנה. הפורט הפנימי נשאר 8080. משתני `HOST` ו-`PORT` של `python app.py` אינם שולטים ב-Gunicorn; פקודת CMD קובעת את ה-bind שלו.

## מה צריך לדעת להסביר?

- `FROM` בוחר בסיס עם Python; `RUN` מתקין תלויות בזמן הבנייה; `COPY` מכניס קוד; `CMD` מפעיל שרת בזמן הריצה.
- משתמש האפליקציה אינו root; לתיקיית הנתונים יש הרשאות כתיבה מתאימות.
- Gunicorn מפעיל worker אחד וארבעה threads לגרסה הקטנה. זה אינו פתרון scale או תור משימות.
- Docker בודק `/health`; מצב healthy אינו אישור שכל האתרים המנוטרים תקינים, וגם אינו מפעיל תיקון אוטומטי.
- אין כאן עדיין אימות משתמשים, CSRF, תזמון בדיקות, CI/CD או פריסה ציבורית. הפורט מפורסם רק למחשב המקומי.
- סודות אינם נכתבים ל-Dockerfile; כל הנתונים והקוד בפרויקט הם נתוני תרגול בלבד.

## תקלה שפגשנו בבנייה המקומית

הורדת Python מ-Docker Hub הצליחה, אבל pip נכשל בחיבור TLS ל-`files.pythonhosted.org`. לא ביטלנו אימות תעודות. הוכנה תיקיית `wheelhouse` מקומית: חבילות Flask ו-MarkupSafe הורדו מ-GitHub Releases הרשמיים, וחבילות תלויות נוספות הועתקו ממטמון מקומי. קובצי ה-wheel האלה אומתו מול SHA-256 שפורסם ב-PyPI. Gunicorn 27.0.1 נבנה מקוד המקור בתג הרשמי של benoitc/gunicorn; זה wheel שנבנה מקומית, לא קובץ wheel מאומת מול PyPI.

כאשר התיקייה הזו זמינה במחשב:

```bash
docker compose build --build-arg OFFLINE_INSTALL=1
docker compose up -d --wait
```

החבילות הבינאריות אינן נשמרות ב-Git. המטמון הנוכחי מכוון ל-Python 3.12 על Linux ARM64; למחשב או גרסה אחרים צריך להכין חבילות תואמות. במחשב עם גישה תקינה ל-PyPI משתמשים בפקודת הבנייה הרגילה. התקנת Gunicorn נמצאת ב-`requirements-container.txt` ונעשית ב-Linux עם Python 3.12; ההרצה המקומית הפשוטה ממשיכה להשתמש רק ב-`requirements.txt`.

## תרגול לראיון

הסבירי מה יקרה להיסטוריה בעת stop/start, בעת החלפת קונטיינר, ובעת מחיקת ה-Volume עצמו.
