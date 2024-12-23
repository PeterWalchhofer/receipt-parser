import io
import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaIoBaseDownload

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import gspread
import numpy as np
import pandas as pd

# Google Drive API setup
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def authenticate():
    """Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
            
    service = build("drive", "v3", credentials=creds)
    gspread_client = gspread.authorize(creds)
    return service, gspread_client


def list_files_in_folder(service, folder_id, suffix=None):
    # List files in a folder
    q = f"'{folder_id}' in parents and trashed=false and mimeType != 'application/vnd.google-apps.spreadsheet'"
    if suffix:
        q += f" and name contains '{suffix}'"
    result = (
        service.files()
        .list(
            q=q,
        )
        .execute()
    )
    files = [*result["files"]]
    # paginate
    while "nextPageToken" in result:
        next_page = (
            service.files()
            .list(
                q=q,
                pageToken=result["nextPageToken"],
            )
            .execute()
        )
        files.extend(next_page.get("files", []))
        result = next_page
    return files


def download_file(service, file_id, destination):
    # Download a file
    request = service.files().get_media(fileId=file_id)
    fh = open(destination, "wb")
    file = io.BytesIO()
    downloader = MediaIoBaseDownload(file, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()

    fh.write(file.getvalue())


def download_folder(service, folder_id, folder_path):
    os.makedirs(folder_path, exist_ok=True)
    files = list_files_in_folder(service, folder_id)
    for file in files:
        file_path = os.path.join(folder_path, file["name"])
        if file["mimeType"] == "application/vnd.google-apps.folder":
            download_folder(service, file["id"], file_path)
        else:
            if not os.path.exists(file_path):
                download_file(service, file["id"], file_path)


def synch_gdrive(service, folder_id):
    month_folders = list_files_in_folder(service, folder_id)
    root = "data"
    for month_folder in month_folders:
        folder_name = month_folder["name"]
        folder_id = month_folder["id"]
        print(f"Downloading {folder_name}")
        download_folder(service, folder_id, os.path.join(root, folder_name))


def upload_gsheet_api(gspread_client, folder_id, pandas_df, directory):
    spreadsheet = gspread_client.create(f"Ausgaben_{directory}", folder_id)
    sheet = spreadsheet.sheet1
    sheet.update_title("Ausgaben")
    # header row bold
    sheet.format("A1:Z1", {"textFormat": {"bold": True}})
    sheet.clear()

    index_tuple_empty = np.where(pandas_df.isnull().values)
    pandas_df = pandas_df.replace({np.nan: "", pd.NaT: ""})
    column_letter_mapping = {
        col: chr(65 + i) for i, col in enumerate(pandas_df.columns)
    }

    sheet.update([pandas_df.columns.values.tolist()] + pandas_df.values.tolist())
    sheet.columns_auto_resize(0, 20)

    
      # Prepare batch requests
    requests = []

    # Header row formatting
    requests.append({
        "repeatCell": {
            "range": {
                "sheetId": sheet.id,
                "startRowIndex": 0,
                "endRowIndex": 1,
                "startColumnIndex": 0,
                "endColumnIndex": len(pandas_df.columns),
            },
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {"bold": True},
                },
            },
            "fields": "userEnteredFormat.textFormat.bold",
        }
    })

    # Format empty cells
    for row_int64, col_int64 in zip(*index_tuple_empty):
        row = int(row_int64)
        col = int(col_int64)
        requests.append({
            "updateCells": {
                "rows": [{
                    "values": [{
                        "userEnteredFormat": {
                            "backgroundColor": {
                                "red": 247 / 255,
                                "green": 153 / 255,
                                "blue": 148 / 255,
                            }
                        }
                    }]
                }],
                "fields": "userEnteredFormat.backgroundColor",
                "range": {
                    "sheetId": sheet.id,
                    "startRowIndex": row + 1,
                    "endRowIndex": row + 2,
                    "startColumnIndex": col,
                    "endColumnIndex": col + 1,
                },
            }
        })

    # Execute batch update for formatting
    spreadsheet.batch_update({"requests": requests})
                
    # Aggregation
    agg_sheet = spreadsheet.add_worksheet("Aggregation", 20, 20)
    agg_sheet.format("A1:Z1", {"textFormat": {"bold": True}})
    agg_sheet.update_acell("A1", "Summe Brutto")
    agg_sheet.update_acell("B1", "Summe Netto")
    agg_sheet.update_acell("C1", "Summe MwSt.")
    gross_col = column_letter_mapping["total_gross_amount"]
    net_col = column_letter_mapping["total_net_amount"]
    vat_col = column_letter_mapping["vat_amount"]
    agg_sheet.update_acell(f"A2", f"=SUM({sheet.title}!{gross_col}2:{gross_col})")
    agg_sheet.update_acell(f"B2", f"=SUM({sheet.title}!{net_col}2:{net_col})")
    agg_sheet.update_acell(f"C2", f"=SUM({sheet.title}!{vat_col}2:{vat_col})")
