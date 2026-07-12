# Dimensur News Automation

Sistema de automatización editorial en Python para generar noticias SEO, crear una imagen única, preparar el JSON de la API propia de Dimensur, publicar la noticia y dejar trazabilidad completa en Google Sheets o en un Excel local.

El proyecto no depende de WordPress. La información corporativa y el catálogo de enlaces internos se leen de archivos externos en cada ejecución, por lo que pueden ampliarse sin tocar el código.

## Qué hace

En cada ejecución:

1. Abre la hoja `Noticias`.
2. Busca la primera fila con `Estado = Crear`.
3. La bloquea de forma operativa cambiándola a `Generando`.
4. Lee `config/info_previa_dimensur.txt` y `config/enlazado_interno.txt`.
5. Recupera la publicación anterior desde la hoja y el historial local.
6. Genera un artículo mediante OpenAI con salida estructurada.
7. Valida longitud, HTML, SEO y que todas las URLs estén permitidas.
8. Compara el nuevo contenido con el anterior mediante TF-IDF/coseno.
9. Regenera si supera el umbral de similitud.
10. Diseña un concepto visual y lo compara con el historial de imágenes.
11. Genera una imagen con OpenAI o un marcador técnico si el dry-run está configurado para no gastar imágenes.
12. Guarda la imagen en `data/images/` y la convierte a base64.
13. Construye el payload sin concatenar JSON manualmente.
14. Guarda el payload completo en `data/payloads/`.
15. En modo publicación, hace `POST` a la API de Dimensur.
16. Actualiza todos los campos de la fila, los historiales y los logs.

Si cualquier paso crítico falla, no se publica y la fila queda en `Error` con una explicación.

## Requisitos

- Python 3.11 o superior.
- Una cuenta/proyecto de OpenAI con acceso a los modelos configurados.
- Una cuenta de servicio de Google si se usa Google Sheets.
- Token Bearer de la API de Dimensur para publicar.

Los modelos se configuran por entorno. Los valores iniciales usan la API Responses con salida estructurada y la API de imágenes de OpenAI. Consulta la [documentación de generación de texto](https://developers.openai.com/api/docs/guides/text), [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) y [generación de imágenes](https://developers.openai.com/api/docs/guides/image-generation).

## Instalación

Desde la carpeta del proyecto:

```bash
python -m venv .venv
```

Activación en Linux/macOS:

```bash
source .venv/bin/activate
```

Activación en Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Instala las dependencias:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Crea el archivo de entorno:

Linux/macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

## Configuración de `.env`

Variables principales:

| Variable | Uso |
|---|---|
| `OPENAI_API_KEY` | Clave de OpenAI. Obligatoria para contenido y planificación visual. |
| `OPENAI_TEXT_MODEL` | Modelo de texto. Valor inicial: `gpt-5.5`. |
| `OPENAI_IMAGE_MODEL` | Modelo de imagen. Valor inicial: `gpt-image-2`. |
| `SHEET_BACKEND` | `google` o `excel`. |
| `GOOGLE_SHEET_URL` | URL completa de Google Sheets. Si se informa, no hace falta copiar el ID por separado. |
| `GOOGLE_SHEET_ID` | ID que aparece en la URL de Google Sheets. |
| `GOOGLE_SHEET_NAME` | Pestaña; por defecto `Noticias`. |
| `GOOGLE_CREDENTIALS_FILE` | Ruta al JSON de la cuenta de servicio. |
| `EXCEL_FILE_PATH` | Ruta usada cuando `SHEET_BACKEND=excel`. |
| `DIMENSUR_API_URL` | Endpoint de publicación. |
| `DIMENSUR_API_TOKEN` | Token Bearer. |
| `DRY_RUN` | Si es `true`, no llama a la API de Dimensur. |
| `GENERATE_IMAGES_IN_DRY_RUN` | Si es `false`, crea un marcador local sin coste de imagen. |
| `MAX_REGENERATION_ATTEMPTS` | Intentos máximos de contenido y concepto visual. |
| `MIN_CONTENT_WORDS` / `MAX_CONTENT_WORDS` | Rango de longitud validado. |
| `CONTENT_SIMILARITY_THRESHOLD` | Umbral de rechazo de artículos. Más bajo = más estricto. |
| `IMAGE_SIMILARITY_THRESHOLD` | Umbral textual de rechazo de conceptos visuales. |
| `TIMEZONE` | Zona usada en las fechas, por defecto `Europe/Madrid`. |

No escribas claves ni tokens en el código. No subas `.env` ni `credentials.json` a Git.

## Credenciales de Google Sheets

1. Crea o selecciona un proyecto en Google Cloud.
2. Activa Google Sheets API y Google Drive API.
3. Crea una cuenta de servicio.
4. Genera una clave JSON y guárdala, por ejemplo, como `credentials.json` en la raíz.
5. Copia el correo de la cuenta de servicio.
6. Comparte el Google Sheet con ese correo y permiso de editor.
7. Copia la URL completa del documento o el ID desde:

   `https://docs.google.com/spreadsheets/d/ESTE_ES_EL_ID/edit`

8. Escribe la URL en `GOOGLE_SHEET_URL` o el ID en `GOOGLE_SHEET_ID`.

La aplicación nunca incluye credenciales reales en el repositorio.

## Preparación de la hoja

La pestaña debe llamarse `Noticias` o coincidir con `GOOGLE_SHEET_NAME`. La fila 1 debe contener estas columnas. Pueden estar en otro orden; si faltan columnas, la aplicación las añade al final al cargar la hoja.

| Cabecera necesaria |
|---|
| ID |
| Título base |
| Keyword principal |
| Estado |
| Contenido HTML |
| Título SEO |
| Metadescripción |
| Slug |
| Categoría |
| Etiquetas |
| Enlaces internos usados |
| Anchors usados |
| Resumen del contenido generado |
| Diferencia frente al artículo anterior |
| Prompt imagen |
| Concepto visual imagen |
| Diferencia visual frente a imagen anterior |
| URL imagen o nombre archivo |
| ALT imagen |
| JSON enviado |
| Respuesta API |
| URL publicada |
| Fecha publicación |
| Error |

Una hoja completamente vacía recibe estas cabeceras automáticamente. Si ya contiene cabeceras parciales, el programa conserva las existentes, reconoce algunos nombres antiguos habituales y añade al final las que falten.

Para crear una noticia basta con rellenar `Título base`, opcionalmente `Keyword principal`, y poner `Crear` exactamente en `Estado`.

## Uso con Excel

Para pruebas locales sin Google:

```env
SHEET_BACKEND=excel
EXCEL_FILE_PATH=data/noticias.xlsx
```

La primera ejecución crea el libro y sus cabeceras. Añade una fila, guarda el archivo y ejecuta el programa. No mantengas el Excel abierto durante la escritura.

## Contexto editorial ampliable

`config/info_previa_dimensur.txt` se carga de nuevo en cada ejecución. Puedes añadir:

- datos corporativos verificados;
- promociones y servicios;
- zonas de actuación;
- pautas de tono;
- restricciones legales o editoriales;
- prioridades SEO.

No hace falta conservar un formato rígido: es texto libre. Evita incluir afirmaciones dudosas, porque el archivo funciona como fuente editorial.

## Enlaces internos ampliables

Añade bloques a `config/enlazado_interno.txt` con este formato:

```text
---

URL: https://www.dimensur.es/ruta-permitida
Nombre: Nombre legible
Temas: tema uno, tema dos, zona
Anchors sugeridos: anchor natural, otro anchor
```

El generador solo puede insertar URLs extraídas de campos `URL:`. Después de generar, el programa vuelve a analizar todos los `href` del HTML y rechaza la pieza si encuentra una URL no autorizada.

## Ejecución

Respeta `DRY_RUN` del `.env`:

```bash
python main.py
```

Fuerza una prueba sin publicar:

```bash
python main.py --dry-run
```

Fuerza publicación real:

```bash
python main.py --publish
```

Procesa una fila concreta:

```bash
python main.py --dry-run --row 5
python main.py --publish --row 5
```

`--dry-run` y `--publish` son mutuamente excluyentes.

Una fila indicada expresamente puede estar en `Crear`, `Generado - No publicado`
o `Error`, lo que permite reintentar un fallo controlado. El programa rechaza
filas ya `Publicadas` o todavía en `Generando`.

Si se ejecuta `--publish` sin `--row`, se aceptan filas en `Crear` y también en `Generado - No publicado`. Esto permite probar una fila y publicarla después. La segunda ejecución regenera y revalida la pieza; no publica a ciegas un marcador de imagen de dry-run.

## Imágenes en dry-run

Con:

```env
GENERATE_IMAGES_IN_DRY_RUN=false
```

el sistema sigue generando y comparando el concepto visual, pero crea un JPEG abstracto local marcado internamente como simulado. Sirve para validar el flujo sin pagar una generación de imagen.

Para probar también la imagen real:

```env
GENERATE_IMAGES_IN_DRY_RUN=true
```

Una publicación real siempre exige una imagen real generada en esa ejecución.

## Payload y límite de las celdas

Una imagen base64 suele ocupar cientos de miles o millones de caracteres. Google Sheets y Excel tienen límites por celda, por lo que el JSON íntegro no cabe de forma fiable en `JSON enviado`.

El sistema:

- guarda el payload íntegro, incluida la imagen base64, en `data/payloads/<slug>.json`;
- escribe en la hoja una copia auditable con `image.data` sustituido por su tamaño;
- incluye en esa copia la ruta `_local_payload_file`;
- guarda la imagen binaria en `data/images/`.

Así no se pierde información y la hoja continúa siendo manejable.

## Estados

- `Crear`: pendiente.
- `Generando`: reservada por una ejecución.
- `Generado - No publicado`: dry-run completado.
- `Subida`: API de Dimensur completada con HTTP 2xx. También se reconocen `Publicado` y `Publicada` como estados históricos de hojas anteriores.
- `Error`: fallo en generación, validación, imagen, hoja o API.

Una fila en `Generando` no se recoge automáticamente para evitar dobles publicaciones. Si una ejecución fue interrumpida y confirmas que no publicó, cambia manualmente su estado a `Crear`.

## Anti-repetición

El control combina varias capas:

- el prompt recibe título, resumen, ángulo, H2, CTA, enlaces y concepto visual anteriores;
- se prohíbe reutilizar estructura, apertura, argumentos, orden y cierre;
- el HTML nuevo se compara con el anterior mediante TF-IDF y similitud coseno;
- los H2 compartidos añaden penalización;
- el concepto visual se compara con la última imagen y el historial;
- si un umbral se supera, se regenera hasta el máximo configurado;
- los resultados aceptados se guardan en `data/historial_publicaciones.json` y `data/imagenes_usadas.json`.

Los umbrales son heurísticos. Conviene revisar varios artículos reales y ajustarlos gradualmente. Un valor más bajo rechaza con mayor facilidad.

## Publicación en la API de Dimensur

El cliente envía:

```http
POST /api/news
Authorization: Bearer <DIMENSUR_API_TOKEN>
Content-Type: application/json
```

Se usa `requests.post(..., json=payload)`, nunca concatenación manual. Solo una respuesta HTTP 2xx marca la fila como `Subida`. Si la respuesta incluye `url`, `published_url`, `public_url` o `link`, incluso dentro de un objeto anidado, se guarda como URL publicada.

Antes del primer uso real, haz un dry-run y confirma con el responsable de la API los nombres exactos y la respuesta del endpoint.

## Logs e historiales

- Log principal: `logs/automation.log`.
- Rotación: 5 MB por archivo, cinco copias.
- Artículos: `data/historial_publicaciones.json`.
- Imágenes: `data/imagenes_usadas.json`.
- Imágenes generadas: `data/images/`.
- Payloads completos: `data/payloads/`.

Para seguir el log en Linux:

```bash
tail -f logs/automation.log
```

En PowerShell:

```powershell
Get-Content .\logs\automation.log -Wait
```

## Despliegue en Hostinger

Para este proyecto, la opción recomendable es un VPS de Hostinger. La automatización no es una web PHP estática: necesita Python 3.11+, instalar dependencias, leer `.env` y `credentials.json`, escribir logs/payloads e invocarse con cron. En hosting web compartido puede haber cron, pero no es el entorno adecuado si no permite crear un entorno Python completo.

En el servidor, sube el proyecto a una ruta no pública, por ejemplo:

```bash
/home/usuario/dimensur-news-automation
```

No lo subas dentro de `public_html` salvo que sepas bloquear el acceso a `.env`, `credentials.json`, `data/` y `logs/`.

Archivos que debes subir/configurar en el servidor:

- todo el proyecto;
- `.env` con `OPENAI_API_KEY`, `GOOGLE_SHEET_URL`, `GOOGLE_SHEET_NAME=Hoja 1` y, si vas a publicar, `DIMENSUR_API_TOKEN`;
- `credentials.json` de Google;
- permisos de editor en la Google Sheet para el `client_email` de `credentials.json`.

Primera preparación por SSH:

```bash
cd /home/usuario/dimensur-news-automation
chmod +x scripts/*.sh
scripts/setup_hostinger_vps.sh
scripts/run_hostinger.sh --dry-run
```

Si el dry-run termina bien, programa cron. Ejemplo semanal los miércoles a las 12:00:

```cron
CRON_TZ=Europe/Madrid
0 12 * * 3 /home/usuario/dimensur-news-automation/scripts/run_hostinger.sh --publish
```

Para seguir el resultado:

```bash
tail -f /home/usuario/dimensur-news-automation/logs/cron.log
tail -f /home/usuario/dimensur-news-automation/logs/automation.log
```

## Si tienes Hostinger normal

Con Hostinger normal, deja Hostinger para la web y ejecuta esta automatización fuera, por ejemplo con GitHub Actions. El archivo `.github/workflows/dimensur-news.yml` ya está preparado para:

- ejecutarse manualmente en modo `dry-run` o `publish`;
- publicar por calendario una única fila con `Estado = Crear` cada miércoles a las 12:00 de Madrid;
- instalar Python y dependencias;
- crear `credentials.json` desde un secret;
- leer/escribir la Google Sheet configurada.

En GitHub, crea estos secrets en `Settings > Secrets and variables > Actions`:

| Secret | Valor |
|---|---|
| `OPENAI_API_KEY` | Tu clave de OpenAI |
| `GOOGLE_CREDENTIALS_JSON` | Contenido completo del `credentials.json` de Google |
| `DIMENSUR_API_TOKEN` | Token de Dimensur, obligatorio para la publicación programada |

Antes de activar el calendario, en `Actions > Dimensur News Automation`, ejecuta `Run workflow` con `mode = dry-run`. La publicación programada solo recoge la primera fila en estado `Crear`; no reutiliza filas `Generado - No publicado`. Si falta `DIMENSUR_API_TOKEN`, el workflow se detiene antes de generar contenido o modificar la hoja.

La ejecución programada usa dos horas UTC candidatas y solo continúa cuando la hora local de Madrid es exactamente las 12:00:

```yaml
- cron: "0 10,11 * * 3"
```

Así mantiene las 12:00 tanto en horario de verano como en horario de invierno.

## Programación con cron

Ejemplo para cada miércoles a las 12:00:

```cron
0 12 * * 3 /ruta/dimensur-news-automation/.venv/bin/python /ruta/dimensur-news-automation/main.py >> /ruta/dimensur-news-automation/logs/cron.log 2>&1
```

Comprueba:

- que la ruta de Python es la del entorno virtual;
- que el usuario de cron puede leer `.env` y `credentials.json`;
- que puede escribir en `data/` y `logs/`;
- que el servidor utiliza `Europe/Madrid` o tiene `CRON_TZ=Europe/Madrid`.

Una alternativa explícita:

```cron
CRON_TZ=Europe/Madrid
0 12 * * 3 cd /ruta/dimensur-news-automation && .venv/bin/python main.py >> logs/cron.log 2>&1
```

En Windows se puede crear una tarea semanal en el Programador de tareas apuntando a:

```text
Programa: C:\ruta\dimensur-news-automation\.venv\Scripts\python.exe
Argumentos: C:\ruta\dimensur-news-automation\main.py
Iniciar en: C:\ruta\dimensur-news-automation
```

## Pruebas

```bash
python -m pytest -q
```

Las pruebas cubren parsing de enlaces, slug, helpers HTML, similitud, payload y el backend Excel. No realizan llamadas reales a OpenAI, Google ni Dimensur.

## Errores comunes

### `OPENAI_API_KEY está vacío`

Crea `.env`, añade la clave y comprueba que ejecutas desde este proyecto.

### Modelo no disponible

Cambia `OPENAI_TEXT_MODEL` o `OPENAI_IMAGE_MODEL` por uno habilitado en tu proyecto de OpenAI. Mantén un modelo compatible con Structured Outputs.

### Error de verificación al generar imágenes

Algunas organizaciones deben completar la verificación en la consola de OpenAI antes de usar modelos GPT Image.

### `GOOGLE_SHEET_ID está vacío`

Completa `GOOGLE_SHEET_URL` o `GOOGLE_SHEET_ID`, o usa temporalmente `SHEET_BACKEND=excel`.

### No se encuentra `credentials.json`

Revisa `GOOGLE_CREDENTIALS_FILE`; la ruta relativa se interpreta desde la raíz del proyecto.

### `SpreadsheetNotFound`

Comprueba el ID y comparte la hoja con el correo de la cuenta de servicio.

### Faltan columnas obligatorias

Corrige la fila 1 según la tabla de cabeceras. Los acentos no son un problema, pero los nombres deben corresponder a los campos documentados.

### No hay noticias pendientes

Es un final normal. Revisa que el estado sea exactamente `Crear`.

### Artículo rechazado por similitud o longitud

Revisa el log. Puedes ampliar `MAX_REGENERATION_ATTEMPTS` o ajustar los umbrales, pero antes conviene mejorar el título base, la keyword y el contexto editorial.

### Error HTTP de Dimensur

La fila queda en `Error` y `Respuesta API` conserva el código y el cuerpo. Revisa URL, token, contrato del endpoint y tamaño admitido para imágenes.

### La API publicó pero la hoja no se actualizó

El log registra un evento crítico con la ruta del payload y la URL conocida. Comprueba primero la web/API para no publicar de nuevo por accidente y actualiza la fila manualmente.

## Seguridad y operación

- Mantén `.env` y `credentials.json` fuera de Git.
- Limita el acceso de la cuenta de servicio a la hoja necesaria.
- Rota el token de Dimensur si se expone.
- Protege `data/payloads/`: contiene las imágenes codificadas y el contenido completo.
- Haz copias de seguridad de los dos historiales.
- Empieza siempre con `--dry-run`.
- Revisa editorialmente las primeras publicaciones antes de activar cron.
