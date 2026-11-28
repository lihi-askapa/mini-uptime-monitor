# גרסת הדגמה ציבורית ב־AWS

## מצב הפריסה — 26 בנובמבר 2026

הגרסה הציבורית הופעלה ב־AWS EC2. המשתמשת אישרה פתיחת אתר ב־HTTPS,
בדיקה ידנית מוצלחת וחסימת בדיקה חוזרת בתוך חלון ההמתנה.
קישור: https://pulse-13-60-191-46.sslip.io/
עשר בדיקות עברו בתוך ה־Image בשרת לפני ההפעלה; גם הגדרות Compose ותחביר קאדי נבדקו.
ההעברה והפריסה בוצעו ידנית. העלאת קוד ל־GitHub מפעילה CI, אך אינה מעדכנת את AWS אוטומטית.

- `Caddyfile`: מגדיר את שם האתר, הצפנת HTTPS אוטומטית והעברת הבקשות לשירות `web` בפורט 8080 ברשת הפנימית של Compose.
- `compose.public.yaml`: מצטרף ל־`compose.yaml`, מוסיף קונטיינר שלישי של קאדי בפורטים הציבוריים 80 ו־443 ומפעיל `PUBLIC_DEMO=1` בשירות web.
- נוספו שני Volumes לקאדי. `caddy-data` מכיל בין השאר תעודות ומפתחות TLS; אין למחוק אותו כחלק מעדכון רגיל. מסד הנתונים נשאר ב־`monitor-data` הקיים.
- נוספה מדיניות הפעלה מחדש לשירותים בהפעלה ציבורית. היא אינה מפעילה מחדש שרת EC2 שנעצר ואינה מתקנת באופן אוטומטי קונטיינר שמסומן unhealthy אבל עדיין רץ.

## הגנות במצב ציבורי

במצב `PUBLIC_DEMO=1`, דף הבית מנפיק אסימון לטופס ומשתמש בעוגיית session חתומה,
מסומנת Secure ו־HttpOnly. בקשת בדיקה בלי אסימון מתאים נדחית ב־400.
הדגמה ציבורית דורשת HTTPS; טופס דרך מנהרת HTTP אינו צפוי לפעול במצב הזה.
השרת משתמש במפתח session אקראי בכל הפעלה, אלא אם הוגדר SECRET_KEY חיצוני.
משאירים תהליך Gunicorn אחד כבקובץ Dockerfile; אם מפתח התחלף, מרעננים את הדף לקבלת טופס ועוגייה חדשים.

SQLite שומר חלון המתנה של 30 שניות לכל אתר, במשותף לכל המבקרים.
הזכות לבדיקה נתפסת בטרנזקציה לפני הבקשה החיצונית. לחיצה מוקדמת מדי מקבלת 429 ו־Retry-After.
המתזמן אינו משתמש בהגבלת הלחיצות, וממשיך לפעול לפי ההגדרה שלו.
בקשות לגוף גדול מ־16 KiB נדחות. זה אינו שירות מוגן מפני DDoS, ואין עדיין סבב מחיקה של היסטוריה ישנה.

נוספו שלוש בדיקות, ובסך הכול עשר:
דחיית טופס ללא אסימון, חלון המתנה שמשותף לשני מבקרים ופג אחרי הזמן, והמשך עבודת המתזמן במצב ציבורי.

## כתובת הדגמה

לשרת הנוכחי אפשר להשתמש בשם `pulse-13-60-191-46.sslip.io`.
שירות DNS חיצוני מתרגם את הכתובת ל־IP המוטמע בשם, ללא רכישת דומיין.
זו כתובת תרגול התלויה בשירות חיצוני ובכתובת הציבורית של EC2. אחרי עצירה והפעלה של השרת,
ה־IP עשוי להשתנות; אז נדרש לעדכן גם את השם והקישורים. לא הוקצתה כתובת Elastic IP.

## מסלול הבנייה הידני המקורי — לתיעוד

הפריסה הפעילה עברה לשימוש באימג׳ מ־ECR. לניהול שלה משתמשים בשלושת הקבצים שבסעיף הבא.

### הפעלה בשרת, אחרי העברת הקבצים ובנייה

יש לוודא תחילה בקונסולת EC2 שכתובת השרת עדיין 13.60.191.46 ושפורטים 80 ו־443 פתוחים לציבור.
את הפעולות הבאות מבצעים בתיקיית הפרויקט בשרת בלבד.

```bash
sudo env DEMO_DOMAIN=pulse-13-60-191-46.sslip.io docker compose -f compose.yaml -f compose.public.yaml --profile monitoring config --quiet
```

בדיקת ההגדרות אינה יוצרת קונטיינרים. כדי לבדוק תחביר קאדי בלי להפעיל אתר:

```bash
sudo docker run --rm --network none -e DEMO_DOMAIN=pulse-13-60-191-46.sslip.io -v "$PWD/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2.11.9-alpine caddy adapt --config /etc/caddy/Caddyfile --adapter caddyfile
```

אחרי שעשר הבדיקות עברו גם ב־Image החדש, מפעילים:

```bash
sudo env DEMO_DOMAIN=pulse-13-60-191-46.sslip.io docker compose -f compose.yaml -f compose.public.yaml --profile monitoring up -d
sudo env DEMO_DOMAIN=pulse-13-60-191-46.sslip.io docker compose -f compose.yaml -f compose.public.yaml --profile monitoring logs --tail=30 caddy
```

משתמשים תמיד באותו צירוף קובצי Compose לניהול הפריסה הציבורית. פתיחת תעודות תלויה ב־DNS,
בגישה ציבורית ובזמינות רשות התעודות; יש לאמת HTTPS בדפדפן מבחוץ אחרי ההפעלה.
בודקים דף בית, health, לחיצה מוצלחת, חסימת לחיצה חוזרת והמשך הופעת נתוני המתזמן.
אין לפרסם את הקישור כהדגמה פעילה לפני האימות.

## מקורות

- https://sslip.io/
- https://caddyserver.com/docs/automatic-https
- https://hub.docker.com/_/caddy

## פריסה מ־ECR — אומתה ב־28 בנובמבר 2026

המשתמשת אימתה שהאתר והמתזמן רצים מהאימג׳ של הקומיט
`d2e621bccaba25bcce26bdb75b8e9b748a6de9fb`, שעשר הבדיקות שבו עברו,
שהכתובת הציבורית החזירה 200 ושהמתזמן השלים סבבים.
בדיקת `/health/monitoring` ו־15 הבדיקות קיימות בינתיים מקומית ולא בפריסה הזאת.

הפקודות הבאות הן מסלול הפריסה, לביצוע בשלבים מתוך תיקיית הפרויקט בשרת.
בכל חלון SSH חדש מגדירים שוב את `APP_IMAGE` לגרסה שנבחרה; אין להשתמש בתג דוגמה לא קיים.
הגרסה המופיעה כאן היא הגרסה הקיימת שאומתה, לא הפריסה של השינוי המקומי החדש.

```bash
export APP_IMAGE=944464821297.dkr.ecr.eu-north-1.amazonaws.com/mini-uptime-monitor:d2e621bccaba25bcce26bdb75b8e9b748a6de9fb
aws ecr get-login-password --region eu-north-1 | sudo docker login --username AWS --password-stdin 944464821297.dkr.ecr.eu-north-1.amazonaws.com
sudo docker pull "$APP_IMAGE"
sudo docker run --rm "$APP_IMAGE" python -m unittest discover -s tests -v
sudo env APP_IMAGE="$APP_IMAGE" DEMO_DOMAIN=pulse-13-60-191-46.sslip.io docker compose -f compose.yaml -f compose.public.yaml -f compose.ecr.yaml --profile monitoring config --images
sudo env APP_IMAGE="$APP_IMAGE" DEMO_DOMAIN=pulse-13-60-191-46.sslip.io docker compose -f compose.yaml -f compose.public.yaml -f compose.ecr.yaml --profile monitoring up -d --no-build
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
curl -i --max-time 15 https://pulse-13-60-191-46.sslip.io/health
sudo docker logs --tail=10 mini-uptime-monitor-scheduler-1
```

השרת משתמש בתפקיד שלו ולא בפרופיל האישי מהמק. ההרשאה מאפשרת משיכת אימג׳ים
מהמאגר של הפרויקט; אינה מאפשרת העלאה אליו. שיוך הפרופיל לשרת בוצע ב־CLI מחוץ ל־Terraform.
יש להעביר גם קובצי הגדרות שהשתנו לשרת; הורדת אימג׳ אינה מעדכנת את קובצי Compose שבשרת.
יש לשמור את שלושת הווליומים. חיבור גיטהאב למאגר כבר אוטומטי, אך הפריסה לשרת עדיין ידנית.
