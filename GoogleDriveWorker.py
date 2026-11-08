import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.auth.exceptions import RefreshError
import tkinter.messagebox as messagebox

from data.ExcelParser import load_excel_with_ids
from data.ExcelEqualer import sync_prices_and_margin, validate_margin_update

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
import sys

def _find_client_secret():
    """Ищет client_secret.json в нескольких вероятных местах."""
    candidates = []

    # 1. Рабочая директория (откуда запустили python Main.py)
    candidates.append(os.path.abspath('client_secret.json'))

    # 2. Директория текущего файла (drive/)
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'client_secret.json'))

    # 3. Корень проекта (на уровень выше drive/)
    candidates.append(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'client_secret.json'
    ))

    # 4. Если приложение собрано PyInstaller'ом
    if getattr(sys, 'frozen', False):
        candidates.append(os.path.join(os.path.dirname(sys.executable), 'client_secret.json'))
        if hasattr(sys, '_MEIPASS'):
            candidates.append(os.path.join(sys._MEIPASS, 'client_secret.json'))

    for path in candidates:
        if os.path.isfile(path):
            return path

    raise FileNotFoundError(
        "Не найден файл client_secret.json.\n\n"
        "Проверьте, что он лежит в одном из мест:\n  - " +
        "\n  - ".join(candidates)
    )


def _find_token_path():
    """token.json кладём рядом с client_secret.json, чтобы всё было в одном месте."""
    secret = _find_client_secret()
    return os.path.join(os.path.dirname(secret), 'token.json')


def authenticate_google_drive():
    CLIENT_SECRET_FILE = _find_client_secret()
    TOKEN_FILE = os.path.join(os.path.dirname(CLIENT_SECRET_FILE), 'token.json')

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                print("Refresh-токен недействителен. Требуется повторный вход.")
                try:
                    os.remove(TOKEN_FILE)
                except OSError:
                    pass
                creds = None

        if not creds:
            messagebox.showinfo(
                "Требуется вход в Google",
                "Срок действия вашего токена доступа истек.\n\n"
                "Сейчас откроется браузер. Пожалуйста, выберите ваш Google-аккаунт "
                "и подтвердите доступ к файлам."
            )
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return creds


def download_file_from_drive(service, filename, save_path):
    results = service.files().list(
        q=f"name='{filename}' and trashed=false",
        pageSize=10, fields="files(id, name)").execute()
    items = results.get('files', [])
    if not items:
        raise FileNotFoundError(f"Файл '{filename}' не найден на Google Диске.")
    file_id = items[0]['id']
    request = service.files().get_media(fileId=file_id)
    with open(save_path, 'wb') as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()


def execute_sinc():
    creds = authenticate_google_drive()
    service = build('drive', 'v3', credentials=creds)

    # Папка, где лежат client_secret.json, token.json и canteen.db
    app_dir = os.path.dirname(_find_client_secret())

    local_menu_file = os.path.join(app_dir, "Меню основное.xlsx")
    local_price_file = os.path.join(app_dir, "Сравнение_продажных_цен_и_себестоимости_undefined.xlsx")
    db_path = os.path.join(app_dir, "canteen.db")

    download_file_from_drive(service, "Меню основное.xlsx", local_menu_file)
    download_file_from_drive(service,
                             "Сравнение_продажных_цен_и_себестоимости_undefined.xlsx",
                             local_price_file)

    load_excel_with_ids(local_menu_file)
    sync_prices_and_margin(
        price_file_path=local_price_file,
        db_path=db_path,
        similarity_threshold=0.85
    )
    validate_margin_update()

    os.remove(local_menu_file)
    os.remove(local_price_file)