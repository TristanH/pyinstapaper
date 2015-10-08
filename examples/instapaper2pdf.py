#!/usr/bin/env python
'''
-Generate PDF files from recently starred Instapaper articles. Requires
-wkhtmltopdf.
'''

import cgi
import datetime
import logging
import os
import subprocess
import sys
import tempfile

from lxml import etree

try:
    import pyinstapaper  # noqa
except ImportError:
    sys.path.insert(
        0, (os.path.join(os.path.dirname(__file__), os.path.pardir)))
from pyinstapaper.instapaper import Instapaper

logging.basicConfig(level=logging.DEBUG)

INSTAPAPER_KEY = ''
INSTAPAPER_SECRET = ''
INSTAPAPER_LOGIN = ''
INSTAPAPER_PASSWORD = ''
PDF_DEST_FOLDER = '/tmp/instapaper'
HIGHLIGHTS_DEST_FOLDER = '/tmp/instapaper/highlights'


def main():
    instapaper = Instapaper(
        INSTAPAPER_KEY, INSTAPAPER_SECRET, with_scraper=True)
    instapaper.login(INSTAPAPER_LOGIN, INSTAPAPER_PASSWORD)
    folder_id = get_folder_id_by_name(instapaper, 'keep')
    bookmarks = instapaper.get_bookmarks(folder_id, 5)
    for ct, bookmark in enumerate(bookmarks):
        bookmark.set_scraped_content()
        pdf_file = create_pdf_from_bookmark(bookmark)
        create_markdown_files_from_highlights(bookmark, pdf_file)
    # bookmark.archive()
    logging.info('Saved %d article PDFs to %s', ct + 1, PDF_DEST_FOLDER)


def get_folder_id_by_name(instapaper, folder_name):
    folders = instapaper.get_folders()
    for folder in folders:
        if folder.title == folder_name:
            return folder.folder_id
    raise Exception('Folder ID for name "%s" not found.' % folder_name)


def create_markdown_files_from_highlights(bookmark, pdf_file):
    highlights = bookmark.get_highlights()
    if not highlights:
        return False
    dest_dir = HIGHLIGHTS_DEST_FOLDER
    filename = os.path.join(dest_dir, 'NOTES - %s.md' % bookmark.title)
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
    text = 'URL: %s\nFile: file://%s' % (bookmark.url, pdf_file)
    with open(filename, 'w') as file_:
        file_.write(text.encode('utf-8'))
        for highlight in highlights:
            text = highlight.text.encode('utf-8')
            note = highlight.note.encode('utf-8') if highlight.note else None
            file_.write('\n\n')
            file_.write('* %s' % text)
            if note:
                file_.write('\n    NOTE: %s' % note)


def create_pdf_from_bookmark(bookmark):
    logging.info('Processing %s', bookmark.title)

    # add some introductory HTML to the page (title, etc.)
    stylesheet_html = ('<head><style>body {font-family: Verdana;'
                       'font-size: 11pt;}</style></head>')
    origin_html = bookmark.get_origin_line()
    additional_html = '<div><h1>%s</h1><p>%s</p>%s</div>' % (
        cgi.escape(bookmark.title),
        cgi.escape(bookmark.url),
        origin_html.rstrip()
    )
    txt = bookmark.get_text()['data']
    txt = txt.decode('utf-8')
    parser = etree.HTMLParser()
    tree = etree.fromstring(txt, parser)
    tree.insert(0, etree.XML(stylesheet_html))
    body = tree.getchildren()[1]
    body.insert(0, etree.XML(additional_html))
    new_html = etree.tostring(tree)

    # create/manage the directory structure for the article
    date = datetime.datetime.fromtimestamp(bookmark.time)
    year_dir = str(date.year)
    month_dir = str(date.month)
    dest_dir = os.path.join(PDF_DEST_FOLDER, year_dir, month_dir)
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
    pdf_filename = os.path.join(dest_dir, '%s.pdf' % bookmark.title)
    tmp_file = tempfile.NamedTemporaryFile(delete=False)
    tmp_file.write(new_html)
    tmp_file.close()
    html_filename = '%s.html' % tmp_file.name
    os.rename(tmp_file.name, html_filename)

    # generate the PDF and cleanup
    pdf_cmd = ['wkhtmltopdf', html_filename, pdf_filename]
    proc = subprocess.Popen(
        pdf_cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    cmd_output, return_code = proc.communicate()

    os.unlink(html_filename)
    return pdf_filename

if __name__ == '__main__':
    main()
