from bs4 import BeautifulSoup
import flickrapi
import fs
import fs.base
import fs.errors
import os
from PIL import Image
from StringIO import StringIO
import requests
import struct
import sys
import tempfile
import traceback

try:
    from config import api_key, api_secret, user_id
except ImportError:
    print 'You need to create a config file!'
    print 'Copy sampleconfig.py to config.py and fill in the values'
    print 'You need to register at www.flickr.com/services/apps/create/'
    print 'You can find your user id in the "Useful Values" section of www.flickr.com/services/api/explore/flickr.activity.userComments'
    sys.exit(1)


@flickrapi.rest_parser('bs4')
def parse_bs4(self, rest_xml):
    """Register BeautifulSoup as a format"""
    xml = BeautifulSoup(rest_xml, features="xml")
    if xml.rsp['stat'] == 'ok':
        return xml.rsp
    raise flickrapi.FlickrError(u'Error: {0}: {1}'.format(xml.rsp.err['code'], xml.rsp.err['msg']))


def clump(l, n):
    """Clump a list into groups of length n (the last group may be shorter than n)"""
    return [l[i:i + n] for i in range(0, len(l), n)]


def data_to_png(bytes):
    """Encode a byte buffer as a png, where the buffer is 8 bytes of the data length, then the data"""
    length = struct.pack('L', len(bytes))
    clumps = clump(length + bytes, 3)
    # pad last list out to 3 elements
    clumps[-1] += "\x00\x00"
    clumps[-1] = clumps[-1][:3]
    clumps = map(lambda t: tuple(map(ord, t)), clumps)
    # create img
    img = Image.new('RGB', (len(clumps), 1))
    img.putdata(map(tuple, clumps))
    return img


def png_to_data(imgdata):
    img = Image.open(StringIO(imgdata))
    bytes = sum(list(img.getdata()), ())
    length, data = ''.join(map(chr, bytes[:8])), bytes[8:]
    return ''.join(map(chr, data[:struct.unpack('L', length)[0]]))

flickr = flickrapi.FlickrAPI(api_key, api_secret)
flickr.token.path = '/tmp/flickrtokens'

(token, frob) = flickr.get_token_part_one(perms='delete')
if not token:
    raw_input("Press ENTER after you authorized this program")
flickr.get_token_part_two((token, frob))

# Register some nicer names for API endpoints
flickr.delete = flickr.photos_delete
flickr.get_sizes = flickr.photos_getSizes
flickr.set_meta = flickr.photos_setMeta
flickr.get_meta = flickr.photos_getInfo


class FlickrFile(object):

    """A file-like object representing a file on flickr. Caches with a StringIO object"""

    def __init__(self, imageid, name, data):
        self.imageid = imageid
        self.name = name
        self.stringio = StringIO(data)
        self.closed = False
        self.newlines = ('\r', '\n', '\r\n')
        self.flush()

    def close(self):
        self.flush()
        self.closed = True

    def _stringio_get_data(self):
        old_seek = self.stringio.tell()
        self.stringio.seek(0)
        data = self.stringio.read()
        self.stringio.seek(old_seek)
        return data

    def flush(self):
        with tempfile.NamedTemporaryFile() as tf:
            data_to_png(self._stringio_get_data()).save(tf, 'png')
            if self.imageid:
                flickr.replace(filename=tf.name, photo_id=self.imageid, title=self.name, description=str(len(data)), format='bs4')
            else:
                self.imageid = flickr.upload(filename=tf.name, title=self.name, description=str(len(data)), format='bs4').photoid.text

    def iter(self):
        return self

    def next(self):
        return self.stringio.next()

    def read(self, size=-1):
        return self.stringio.read(size)

    def readline(self, size=-1):
        return self.stringio.read(size)

    def seek(self, offset, whence=0):
        return self.stringio.seek(offset, whence)

    def tell(self):
        return self.stringio.tell()

    def truncate(self, size=0):
        return self.stringio.truncate(size)

    def write(self, data):
        return self.stringio.write(data)

    def writelines(self, seq):
        return self.stringio.writelines(seq)


class FlickrFS(fs.base.FS):

    """A PyFilesystem object representing your flickr account"""

    def __init__(self):
        super(FlickrFS, self).__init__()
        self._flickr_name_cache = {}

    def _norm_path(self, path):
        if path.startswith('/'):
            path = path[1:]
        if path.endswith('/'):
            path = path[:-1]
        return path

    def _lookup_flickr_title(self, title):
        title = self._norm_path(title)
        if title in self._flickr_name_cache:
            fid = self._flickr_name_cache[title]
            try:
                flickr_title = flickr.get_meta(photo_id=fid, format='bs4').title.text
                if flickr_title == title:
                    return fid
            except:
                pass
        for photo in flickr.walk(user_id=user_id):
            if photo.get('title') == title:
                self._flickr_name_cache[title] = photo.get('id')
                return photo.get('id')
        return None

    def open(self, path, mode='r'):  # ignore mode because wdgaf
        path = self._norm_path(path)
        fid = self._lookup_flickr_title(path)
        data = ''
        if fid:
            url = flickr.get_sizes(photo_id=fid, format='bs4').sizes.find('size', label='Original')['source']
            data = png_to_data(requests.get(url).content)
        return FlickrFile(fid, path, data)

    def exists(self, path):
        if path in ('', '/'):
            return True
        return self._lookup_flickr_title(path) is not None

    def isfile(self, path):
        path = self._norm_path(path)
        return path not in ('', '/') and exists(path)

    def isdir(self, path):
        return path in ('', '/')

    def listdir(self, path='/', wildcard=None, full=False, absolute=False, dirs_only=False, files_only=False):
        if path not in ('', '/'):
            raise fs.errors.ResourceNotFoundError(path)
        paths = [unicode(self._norm_path(photo.get('title'))) for photo in flickr.walk(user_id=user_id)]
        return self._listdir_helper(path, paths, wildcard, full, absolute, dirs_only, files_only)

    def makedir(self, path):
        raise ValueError('FlickrFS does not support creating directories')

    def remove(self, path):
        if path in ('', '/'):
            raise fs.errors.ResourceInvalidError(path)
        path = self._norm_path(path)
        if path in self._flickr_name_cache:
            del self._flickr_name_cache[path]
        fid = self._lookup_flickr_title(path)
        if not fid:
            raise fs.errors.ResourceNotFoundError(path)
        flickr.delete(photo_id=fid, format='bs4')

    def removedir(self, path, recursive=False, force=False):
        raise ValueError('FlickrFS does not support creating directories, so why are you removing them?')

    def rename(self, src, dst):
        if src in ('', '/') or dst in ('', '/'):
            raise ResourceInvalidError('Can\'t rename root')
        src = self._norm_path(src)
        dst = self._norm_path(dst)
        fid = self._lookup_flickr_title(src)
        if not fid:
            raise ResourceNotFoundError(src)
        flickr.set_meta(photo_id=fid, title=dst, format='bs4')

    def getinfo(self, path):
        if path in ('', '/'):
            return {'size': 0}
        path = self._norm_path(path)
        fid = self._lookup_flickr_title(path)
        if fid:
            url = flickr.get_sizes(photo_id=fid, format='bs4').sizes.find('size', label='Original')['source']
            data = png_to_data(requests.get(url).content)
            return {'size': len(data)}
        else:
            raise fs.errors.ResourceNotFoundError(path)
