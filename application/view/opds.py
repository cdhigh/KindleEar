#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# Simple OPDS endpoints for EPUB downloads of saved books
import io, os, time, zipfile
from xml.etree import ElementTree as ET
from flask import Blueprint, request, current_app as app, url_for, Response, send_file
from ..view.reader import GetSavedOebList, ExtractBookMeta

bpOpds = Blueprint('bpOpds', __name__, url_prefix='/opds')

ATOM_NS = 'http://www.w3.org/2005/Atom'
OPDS_ACQ = 'http://opds-spec.org/acquisition'

def _ns(tag, ns=ATOM_NS):
    return '{%s}%s' % (ns, tag)


@bpOpds.route('/<username>/catalog.xml')
def Catalog(username: str):
    """Return a minimal OPDS/Atom feed listing saved books for `username`.

    Each entry contains an acquisition link to download the EPUB (generated on-the-fly).
    """
    ebook_dir = app.config.get('EBOOK_SAVE_DIR')
    if not ebook_dir:
        return ('Online reading not enabled', 404)

    user_dir = os.path.join(ebook_dir, username)
    if not os.path.isdir(user_dir):
        return ('User not found or no saved books', 404)

    # Build feed
    ET.register_namespace('', ATOM_NS)
    root = ET.Element(_ns('feed'))
    title = ET.SubElement(root, _ns('title'))
    title.text = f"KindleEar saved books for {username}"
    updated = ET.SubElement(root, _ns('updated'))
    updated.text = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    # iterate saved books structure
    days = GetSavedOebList(user_dir)
    for day in days:
        for book in day.get('books', []):
            entry = ET.SubElement(root, _ns('entry'))
            e_id = ET.SubElement(entry, _ns('id'))
            e_id.text = f"urn:kindleear:{username}:{book.get('bookDir')}"
            e_title = ET.SubElement(entry, _ns('title'))
            e_title.text = book.get('title') or book.get('bookDir')
            # use the date (day) as updated
            e_updated = ET.SubElement(entry, _ns('updated'))
            # try to use file mtime of content.opf if exists
            try:
                opf_path = os.path.join(app.config['EBOOK_SAVE_DIR'], username, book.get('bookDir'), 'content.opf')
                mtime = os.path.getmtime(opf_path) if os.path.exists(opf_path) else time.time()
            except Exception:
                mtime = time.time()
            e_updated.text = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(mtime))

            # link for acquisition (epub)
            href = url_for('bpOpds.Download', username=username, bookpath=book.get('bookDir'), _external=True)
            link = ET.SubElement(entry, _ns('link'))
            link.set('rel', OPDS_ACQ)
            link.set('href', href)
            link.set('type', 'application/epub+zip')

    xml = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    return Response(xml, mimetype='application/atom+xml; charset=utf-8')


@bpOpds.route('/<username>/download/<path:bookpath>')
def Download(username: str, bookpath: str):
    """Generate an EPUB by zipping the saved book directory and return it as an .epub file.

    `bookpath` should be the same prefix returned by the reader (date/bookid).
    """
    ebook_dir = app.config.get('EBOOK_SAVE_DIR')
    if not ebook_dir:
        return ('Online reading not enabled', 404)

    # sanitize path
    if '..' in bookpath:
        return ('Invalid path', 400)

    book_dir = os.path.join(ebook_dir, username, bookpath)
    if not os.path.isdir(book_dir):
        return ('Book not found', 404)

    # Create epub in-memory as a zip
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for root_dir, dirs, files in os.walk(book_dir):
            for fname in files:
                full = os.path.join(root_dir, fname)
                # archive path should be relative to book_dir
                arcname = os.path.relpath(full, book_dir)
                # normalize to forward slashes
                arcname = arcname.replace('\\', '/')
                zf.write(full, arcname)

    bio.seek(0)
    # derive filename
    safe_name = bookpath.replace('/', '_')
    filename = f"{safe_name}.epub"
    return send_file(bio, mimetype='application/epub+zip', as_attachment=True, download_name=filename)
