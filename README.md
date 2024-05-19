# Receipt parser

This is a little script that passes a list of receipts in google drive to chatgpt in order to extract information like
total gross amount, total net amount, total vat, date, company.

The resulting google sheet is a table with all values listed and a link to the original image for you to double-check.
Empty values are marked red. Basic aggregation statistics are saved in a second worksheet.

## Authentication
1. Follow the [instructions](https://developers.google.com/drive/api/quickstart/python) for setting up a project and creating an OAuth 2.0 Client ID.
2. Make sure that you enable ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
3. Download the credentials, rename them to `credentials.json` and put them in the project root.
4. Get OpaneAI API key and put it .env file. See .env.example for reference.

## Data Requirements
The receipts should either be imgages or pdfs. If a receipt is in multiple files, you can name them like `{data_name}_1.jpg`, `{data_name}_2.jpg`.
PDFs are transformed into images using pdf2image utilizing this naming scheme for multiple pages. Make sure you have installed poppler (see [docs](https://pdf2image.readthedocs.io/en/latest/installation.html)).
The Folder root that you use to call the cli, assumes to have sub-folders for each month. In those folders are the actual receipts stored.
For each month a single spreadsheet is generated.
The structure should look like this:
```
root
│-- 2021-01
│   │-- receipt_1.jpg
│   │-- receipt_2.jpg
│-- 2021-02
│   │-- receipt_1.jpg
│   │-- receipt_2.pdf
```

## Usage
1. Install the requirements with `pip install -r requirements.txt`
2. Run the script with `python -m receipt_parser --folder_id <your_folder_id>`. The folder ID of the google drive folder can be found in the URL.
3. The script will create a google sheet for each month and fill it with the extracted information.

