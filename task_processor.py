import os
from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
from magic_pdf.config.enums import SupportedPdfParseMethod
from magic_pdf.data.read_api import read_local_images

OUTPUT_DIR = "output"


def process_pdf(file_path: str) -> str:
    try:
        local_image_dir = f"{OUTPUT_DIR}/images"
        image_dir = os.path.basename(local_image_dir)

        image_writer = FileBasedDataWriter(local_image_dir)

        reader = FileBasedDataReader("")
        pdf_bytes = reader.read(file_path)

        ds = PymuDocDataset(pdf_bytes)

        if ds.classify() == SupportedPdfParseMethod.OCR:
            infer_result = ds.apply(doc_analyze, ocr=True)
            pipe_result = infer_result.pipe_ocr_mode(image_writer)
        else:
            infer_result = ds.apply(doc_analyze, ocr=False)
            pipe_result = infer_result.pipe_txt_mode(image_writer)

        md_content = pipe_result.get_markdown(image_dir)
        return md_content

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


def process_image(file_path: str) -> str:
    try:
        local_image_dir = f"{OUTPUT_DIR}/images"
        image_dir = os.path.basename(local_image_dir)

        image_writer = FileBasedDataWriter(local_image_dir)

        ds = read_local_images(file_path)[0]
        result = ds.apply(doc_analyze, ocr=True).pipe_ocr_mode(image_writer)
        return result.get_markdown(image_dir)

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
