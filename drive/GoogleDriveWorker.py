import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

# Ваши исходные импорты
from data.ExcelParser import load_excel_with_ids
from data.ExcelEqualer import sync_prices_and_margin, validate_margin_update

# Область доступа для Google Drive API (только чтение файлов)
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']


def authenticate_google_drive():
    """Аутентификация в Google Drive API"""
    creds = None
    # Файл token.json сохраняет данные для повторного входа
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # Если нет валидных данных, запросите у пользователя авторизацию
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Используйте ваш JSON с данными учетной записи
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Сохраните данные для следующего запуска
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds


def download_file_from_drive(service, filename, save_path):
    """Скачивает файл с Google Диска по имени"""
    # Найдите файл по имени
    results = service.files().list(
        q=f"name='{filename}' and trashed=false",
        pageSize=10, fields="files(id, name)").execute()
    items = results.get('files', [])

    if not items:
        raise FileNotFoundError(f"Файл '{filename}' не найден на Google Диске.")

    # Скачайте первый найденный файл с таким именем
    file_id = items[0]['id']
    request = service.files().get_media(fileId=file_id)

    with open(save_path, 'wb') as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()


def execute_sinc():
    # 1. Аутентификация
    creds = authenticate_google_drive()
    service = build('drive', 'v3', credentials=creds)

    # 2. Скачивание файлов с Google Диска
    # Локальные имена для сохранения
    local_menu_file = "Меню основное.xlsx"
    local_price_file = "Сравнение_продажных_цен_и_себестоимости_undefined.xlsx"

    # Скачивание основного меню
    download_file_from_drive(service, "Меню основное.xlsx", local_menu_file)

    # Скачивание файла для сравнения цен
    download_file_from_drive(service,
                             "Сравнение_продажных_цен_и_себестоимости_undefined.xlsx",
                             local_price_file)

    # 3. Используйте скачанные файлы
    load_excel_with_ids(local_menu_file)

    results = sync_prices_and_margin(
        price_file_path=local_price_file,
        db_path='canteen.db',
        similarity_threshold=0.85
    )

    # 4. Проверка результатов
    validate_margin_update()

    # 5. (Опционально) Удалите временные файлы
    os.remove(local_menu_file)
    os.remove(local_price_file)


if __name__ == "__main__":
    execute_sinc()