#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import logging
import os

from flask import jsonify, render_template, Blueprint, request, make_response
from werkzeug.utils import secure_filename
import hashlib

from pydrop.config import config

blueprint = Blueprint('templated', __name__, template_folder='templates')

log = logging.getLogger('pydrop')


@blueprint.route('/')
@blueprint.route('/index')
def index():
    # Route to serve the upload form
    return render_template('index.html',
                           page_name='Main',
                           project_name="pydrop")

@blueprint.route('/remove', methods=['POST'])
def remove():
    if request.headers['Content-Type'] != 'application/json':
        return make_response(jsonify(message='Invalid parameter(json)'), 400)
    data = request.get_json()
    log.debug(data)
    filename, file_extension = os.path.splitext(data.get('filename'))
    filename = hashlib.md5(data.get('filename').encode()).hexdigest()
    save_path = os.path.join(config.data_dir, filename + file_extension)

    try:
        os.remove(save_path)
    except OSError as e: # this would be "except OSError, e:" before Python 2.6
        if e.errno != errno.ENOENT: # errno.ENOENT = no such file or directory
            return make_response(jsonify(message=f'remove {save_path} failed'), 400)

    return make_response(jsonify(message='removed successful', data=data), 200)

@blueprint.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    log.debug(file.filename)
    filename, file_extension = os.path.splitext(file.filename)
    filename = hashlib.md5(file.filename.encode()).hexdigest()
    save_path = os.path.join(config.data_dir, filename + file_extension)
    data_url = f'http://{request.host}/{config.data_url}/{filename}{file_extension}' 
    current_chunk = int(request.form['dzchunkindex'])

    # If the file already exists it's ok if we are appending to it,
    # but not if it's new file that would overwrite the existing one
    if os.path.exists(save_path) and current_chunk == 0:
        # 400 and 500s will tell dropzone that an error occurred and show an error
        return make_response(('File already exists', 400))

    try:
        with open(save_path, 'ab') as f:
            f.seek(int(request.form['dzchunkbyteoffset']))
            f.write(file.stream.read())
    except OSError:
        # log.exception will include the traceback so we can see what's wrong
        log.exception('Could not write to file')
        return make_response(("Not sure why,"
                              " but we couldn't write the file to disk", 500))

    total_chunks = int(request.form['dztotalchunkcount'])

    if current_chunk + 1 == total_chunks:
        # This was the last chunk, the file should be complete and the size we expect
        if os.path.getsize(save_path) != int(request.form['dztotalfilesize']):
            log.error(f"File {file.filename} was completed, "
                      f"but has a size mismatch."
                      f"Was {os.path.getsize(save_path)} but we"
                      f" expected {request.form['dztotalfilesize']} ")
            return make_response(('Size mismatch', 500))
        else:
            log.info(f'File {file.filename} has been uploaded successfully')
    else:
        log.debug(f'Chunk {current_chunk + 1} of {total_chunks} '
                  f'for file {file.filename} complete')

    # return make_response((f"Chunk upload successful", 200))
    return make_response(jsonify(message='Chunk upload successful', file=data_url), 200)

