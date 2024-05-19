import typer
from openai import OpenAI
from receipt_parser.entitites.receipt import Receipt
from receipt_parser.llm import get_prompt
from receipt_parser.google import (
    authenticate,
    upload_gsheet_api,
    list_files_in_folder,
    synch_gdrive,
)
from itertools import groupby
import json
import glob
import pandas as pd
import pdf2image
import re

import os

cli = typer.Typer(pretty_exceptions_enable=False)


def pdf_to_jpg():
    pdf_paths = glob.glob("data/*/*.pdf")
    mapping = {}
    for pdf_path in pdf_paths:
        print(f"Converting {pdf_path}")
        images = pdf2image.convert_from_path(pdf_path)
        for i, image in enumerate(images):
            path = pdf_path.replace(".pdf", f"_{i}.jpeg")
            image.save(path, "JPEG")
            mapping[path] = pdf_path
    return mapping


def extract_part_suffix_if_exists(file_name):
    match = re.search(r"_\d.jpeg|_\d.png|_\d.jpg", file_name)
    if match:
        # removed matched
        shortened = file_name.replace(match.group(), "")
        return shortened
    return file_name


def file_id_to_url(file_id):
    return f"https://drive.google.com/file/d/{file_id}/view"


@cli.command()
def scan_receipts(
    folder_id: str = typer.Option(
        "1BBOYB4PABOBl0Obwt8QSrcAPzWffa9HE", help="Google Drive folder ID"
    ),
):
    authenticate()
    synch_gdrive(folder_id)
    mapping = pdf_to_jpg()

    client = OpenAI()

    gdrive_dirs = list_files_in_folder(folder_id)
    for dir_obj in gdrive_dirs:
        subdir = dir_obj["name"]
        image_paths_gdrive = {
            file["name"]: file for file in list_files_in_folder(dir_obj["id"])
        }
        image_paths = sorted(glob.glob(f"data/{subdir}/*.jpeg"))
        grouped_image_paths = [
            list(g)
            for k, g in groupby(image_paths, lambda x: extract_part_suffix_if_exists(x))
        ]
        df_img_urls = []
        df_img_paths = []

        receipts = []
        for img_paths in grouped_image_paths:
            pdf = mapping.get(img_paths[0], None)

            if pdf:
                file_name_pdf = os.path.basename(pdf)
                pdf_gdrive = image_paths_gdrive[file_name_pdf]
                img_urls = [file_id_to_url(pdf_gdrive["id"])]
                file_names = [file_name_pdf]
            else:
                file_names = [os.path.basename(img_path) for img_path in img_paths]
                img_urls = [
                    file_id_to_url(image_paths_gdrive[file_name]["id"])
                    for file_name in file_names
                ]

            df_img_paths.append(file_names)
            df_img_urls.append(img_urls)

            response = client.chat.completions.create(**get_prompt(img_paths))
            json_raw = response.choices[0].message.content
            json_dict = json.loads(json_raw)
            receipt = Receipt(**json_dict)
            receipts.append(receipt)

        csv_path = f"parsed/{subdir}.csv"
        jsons = [receipt.dict() for receipt in receipts]
        df = pd.DataFrame(jsons)
        df["img_url"] = ["\n".join(path_group) for path_group in df_img_urls]
        df["img_path"] = ["\n".join(path_group) for path_group in df_img_paths]

        df.to_csv(csv_path, index=False)

        df = pd.read_csv(csv_path)
        print(f"Uploading {csv_path}")

        upload_gsheet_api(dir_obj["id"], df, subdir)
